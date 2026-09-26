"""
Ujian yang waktunya habis tetapi tidak pernah dikirim (layar ditutup, ponsel
mati) ditutup server; statusnya tidak tertinggal "sedang mengerjakan".
"""
from datetime import datetime as dt, timedelta
from unittest.mock import AsyncMock, patch

import pytest

import repository.hr_recruitment_repository as r
from repository.hr_recruitment_repository import (
    HrRecruitmentRepository as Repo,
    TENGGANG_KIRIM_DETIK,
    TENGGANG_TUTUP_DETIK,
    lewat_batas,
)


def test_lewat_batas():
    t0 = dt(2026, 9, 22, 8, 0)
    assert not lewat_batas(t0, 90, t0 + timedelta(minutes=89))
    assert lewat_batas(t0, 90, t0 + timedelta(minutes=91))
    # tenggang menahan penutupan
    assert not lewat_batas(t0, 90, t0 + timedelta(minutes=91), 180)
    assert not lewat_batas(None, 90, t0)


def test_tenggang_tutup_lebih_panjang_dari_tenggang_kirim():
    # Kiriman layar (membawa ketikan terakhir) harus sempat menang.
    assert TENGGANG_TUTUP_DETIK > TENGGANG_KIRIM_DETIK


@pytest.mark.asyncio
async def test_hanya_yang_lewat_ditutup_dengan_submitted_at_batasnya():
    kini = dt.now()
    lama = {"id": 1, "startedAt": kini - timedelta(hours=5), "durationMinutes": 90}
    jalan = {"id": 2, "startedAt": kini - timedelta(minutes=10), "durationMinutes": 90}
    with patch.object(r.database, "fetch_all", AsyncMock(return_value=[lama, jalan])), \
         patch.object(r.database, "execute", AsyncMock()) as ex:
        n = await Repo.tutup_yang_habis_waktu()
    assert n == 1 and ex.await_count == 1
    q = ex.await_args.args[0]
    nilai = q.compile().params
    assert nilai["submittedAt"] == lama["startedAt"] + timedelta(minutes=90)
    assert "submittedAt\" IS NULL" in str(q)


@pytest.mark.asyncio
async def test_galat_tidak_menggagalkan_daftar():
    with patch.object(r.database, "fetch_all", AsyncMock(side_effect=RuntimeError("x"))):
        assert await Repo.tutup_yang_habis_waktu() == 0


def test_dipanggil_saat_daftar_dan_lembar_dibaca():
    import controllers.hr_recruitment_controller as c
    s = open(c.__file__).read()
    for nama in ("daftar_pelamar", "ringkasan_pelamar", "lembar_jawaban", "pelamar_dari_token"):
        j = s.index(f"HrRecruitmentRepository.{nama}(")
        i = s.rindex("async def ", 0, j)
        assert "tutup_yang_habis_waktu()" in s[i:j], nama


def test_kirim_memakai_tenggang():
    s = open(r.__file__).read()
    i = s.index("async def kirim_ujian(")
    assert "tenggang_detik=TENGGANG_KIRIM_DETIK" in s[i:s.index("@staticmethod", i)]
