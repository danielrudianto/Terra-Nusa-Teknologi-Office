"""
Kolom urut yang tidak dikenal (mis. dari alamat yang disunting tangan) dulu
menjatuhkan daftar pinjaman & aset jadi 500. Kini diabaikan / kembali ke
urutan bawaan.
"""

import pytest

from repository.loan_repository import LoanRepository


@pytest.mark.asyncio
async def test_pinjaman_kolom_urut_asing(fake_db):
    db = fake_db("repository.loan_repository")
    db.queue("fetch_all", [])
    db.queue("fetch_val", 0)
    hasil = await LoanRepository.get_loans(0, 10, False, False, "kolomNgawur", "desc")
    assert "error" not in hasil and hasil.get("count") == 0
    sql = " ".join(str([q for m, q in db.calls if m == "fetch_all"][0]).split())
    assert "ORDER BY loans.date DESC" in sql


@pytest.mark.asyncio
async def test_aset_kolom_urut_asing(fake_db):
    from repository.asset_repository import AssetRepository

    db = fake_db("repository.asset_repository")
    db.queue("fetch_all", [])
    db.queue("fetch_val", 0)
    hasil = await AssetRepository.get_assets(0, 10, None, "kolomNgawur", "asc")
    assert not (isinstance(hasil, dict) and hasil.get("status") == 500), hasil
