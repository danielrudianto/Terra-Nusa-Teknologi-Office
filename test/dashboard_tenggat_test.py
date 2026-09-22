"""
Tenggat dasbor: izin per sumber, yang terlewat ikut ditandai, tanggal pajak.
"""

from datetime import date
from unittest.mock import patch

import pytest

from repository import dashboard_tenggat_repository as m


def test_tanggal_pajak_pmk81():
    # Jendela 22–29 Sep 2026: tidak ada tanggal 15/20; akhir bulan belum.
    assert m.tenggat_pajak(date(2026, 9, 22), date(2026, 9, 29)) == []
    # 25 Sep – 2 Okt: PPN masa Agustus disetor & dilapor 30 Sep.
    t = m.tenggat_pajak(date(2026, 9, 25), date(2026, 10, 2))
    assert t == [
        {"jenis": "pajak", "kode": "ppnSetorLapor", "tanggal": "2026-09-30", "masa": "2026-08", "lewat": False}
    ]
    # 10–20 Jan 2027: masa Desember 2026, PPh setor 15, lapor 20.
    kode = [(x["kode"], x["masa"]) for x in m.tenggat_pajak(date(2027, 1, 10), date(2027, 1, 20))]
    assert kode == [("pphSetor", "2026-12"), ("pphLapor", "2026-12")]


@pytest.mark.asyncio
async def test_sumber_tanpa_izin_tidak_muncul_dan_lewat_ditandai():
    izin = {"payment_plan"}

    async def boleh(user, modul, aksi):
        return modul in izin

    kemarin = date.fromordinal(date.today().toordinal() - 1).isoformat()

    async def rencana(dari, sampai):
        return [{"tanggal": kemarin, "jumlah": 2, "nilai": 5.0}]

    async def meledak(dari, sampai):
        raise AssertionError("sumber tanpa izin tidak boleh dikueri")

    with patch("utils.permission.is_allowed", boleh), \
         patch.object(m.DashboardTenggatRepository, "rencana_keluar", rencana), \
         patch.object(m.DashboardTenggatRepository, "pembayaran_terjadwal", meledak), \
         patch.object(m.DashboardTenggatRepository, "hutang_jatuh_tempo", meledak), \
         patch.object(m.DashboardTenggatRepository, "tender_tutup", meledak):
        h = await m.kumpulkan_tenggat({"id": 1}, 7)
    assert [x["jenis"] for x in h["item"]] == ["rencanaKeluar"]
    assert h["item"][0]["lewat"] is True
    assert h["gagal"] == []


@pytest.mark.asyncio
async def test_sumber_gagal_disebut_bukan_kosong():
    async def boleh(user, modul, aksi):
        return modul == "tender"

    async def rusak(dari, sampai):
        raise RuntimeError("kolom hilang")

    with patch("utils.permission.is_allowed", boleh), \
         patch.object(m.DashboardTenggatRepository, "tender_tutup", rusak):
        h = await m.kumpulkan_tenggat({"id": 1}, 7)
    assert h["gagal"] == ["tenderTutup"] and h["item"] == []
