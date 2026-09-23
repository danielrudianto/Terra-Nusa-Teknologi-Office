"""
Dari tampilan Pembelian harus ada jalan ke CoP yang menagihkannya.

Pembelian menyimpan `certificateOfPaymentID`, tetapi id saja tidak dapat
ditampilkan — yang membukanya ingin tahu CoP MANA. Tanpa nomornya, satu-
satunya jalan ke dokumen penagihnya adalah mencarinya sendiri di halaman
CoP, padahal kaitannya sudah tersimpan.
"""
from unittest.mock import AsyncMock, patch

import pytest

import repository.purchase_repository as pr
from repository.purchase_repository import PurchaseRepository


async def _kueri_detail():
    """Jalankan pembacaan detail dan kembalikan SQL-nya sebagai teks."""
    tangkap = {}

    async def fetch_one(q, *a, **k):
        tangkap["q"] = str(q)
        return None  # 404; yang diperiksa kuerinya, bukan hasilnya

    with patch.object(pr.database, "fetch_one", AsyncMock(side_effect=fetch_one)):
        await PurchaseRepository.get_by_id(7)
    return tangkap.get("q", "")


@pytest.mark.asyncio
async def test_detail_pembelian_membawa_nomor_cop():
    sql = await _kueri_detail()
    assert "certificate_of_payment_name" in sql


@pytest.mark.asyncio
async def test_sambungan_cop_adalah_outer_join():
    """
    Pembelian yang belum tertaut CoP jumlahnya jauh lebih banyak daripada
    yang sudah. Sambungan biasa membuat semuanya hilang dari layar detail —
    404 pada dokumen yang jelas ada.
    """
    sql = (await _kueri_detail()).lower()
    potong = sql[sql.index("certificate_of_payments"):] if "certificate_of_payments" in sql else ""
    assert "left outer join certificate_of_payments" in sql or "left join certificate_of_payments" in sql, sql
