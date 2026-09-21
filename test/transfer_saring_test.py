"""
Daftar transfer antar rekening: saring rekening (asal ATAU tujuan) dan kata
kunci (keterangan + nama/nomor rekening). Hitungan memakai sambungan yang sama
— tanpa itu, penyaring kata kunci pada kolom rekening membuat COUNT gagal.
Diverifikasi juga di MariaDB sungguhan.
"""

from datetime import datetime

import pytest

from repository.interpayment_repository import InterpaymentRepository

MODUL = "repository.interpayment_repository"
A, B = datetime(2026, 9, 1), datetime(2026, 9, 30)


def _sql(db, metode):
    return [" ".join(str(q).split()) for m, q in db.calls if m == metode]


@pytest.mark.asyncio
async def test_saring_rekening_asal_atau_tujuan(fake_db):
    db = fake_db(MODUL)
    db.queue("fetch_all", [])
    db.queue("fetch_val", 0)
    await InterpaymentRepository.get_interpayments(
        1, 10, A, B, {"bankAccountID": 7}, "date", "desc"
    )
    sql = _sql(db, "fetch_all")[0]
    assert '"bankAccountIDOrigin" =' in sql or "bankAccountIDOrigin =" in sql
    assert " OR " in sql


@pytest.mark.asyncio
async def test_kata_kunci_ikut_ke_hitungan_beserta_sambungannya(fake_db):
    db = fake_db(MODUL)
    db.queue("fetch_all", [])
    db.queue("fetch_val", 0)
    await InterpaymentRepository.get_interpayments(
        1, 10, A, B, {"keyword": "kas"}, "date", "desc"
    )
    hitung = _sql(db, "fetch_val")[0]
    assert "LIKE" in hitung and "JOIN" in hitung, hitung


@pytest.mark.asyncio
async def test_kolom_urut_asing_tidak_menjatuhkan(fake_db):
    db = fake_db(MODUL)
    db.queue("fetch_all", [])
    db.queue("fetch_val", 0)
    hasil = await InterpaymentRepository.get_interpayments(
        1, 10, A, B, {}, "kolomNgawur", "desc"
    )
    assert "error" not in hasil
