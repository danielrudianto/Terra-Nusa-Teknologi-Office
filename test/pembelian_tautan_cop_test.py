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


async def _kueri_daftar():
    """
    Jalankan pembacaan DAFTAR dan kembalikan SQL-nya sebagai teks.

    Daftar dan detail dibaca dua kueri yang berbeda, dan itulah sebabnya ini
    ditulis terpisah: nomor CoP sempat hanya ada di detail, sehingga daftar
    pembelian tidak dapat menunjukkan pembelian mana yang berasal dari CoP
    tanpa membuka baris satu per satu.
    """
    tangkap = {}

    async def fetch_all(q, *a, **k):
        tangkap["q"] = str(q)
        return []

    async def fetch_val(q, *a, **k):
        return 0

    with patch.object(pr.database, "fetch_all", AsyncMock(side_effect=fetch_all)), \
         patch.object(pr.database, "fetch_val", AsyncMock(side_effect=fetch_val)):
        hasil = await PurchaseRepository.get_all(0, 25, {}, "date", "desc", None)
    return tangkap.get("q", ""), hasil


@pytest.mark.asyncio
async def test_daftar_pembelian_membawa_nomor_cop():
    sql, hasil = await _kueri_daftar()
    assert "error" not in hasil, hasil
    assert "certificate_of_payment_name" in sql, sql


@pytest.mark.asyncio
async def test_daftar_membawa_keadaan_terhapus_cop():
    """
    Nomornya saja tidak cukup: CoP yang sudah dihapus tetap harus terbaca
    nomornya, tetapi TIDAK boleh menawarkan tautan ke dokumen yang tidak
    dapat dibuka lagi. Layar hanya dapat membedakan keduanya bila keadaan
    hapusnya ikut dikirim.
    """
    sql, _ = await _kueri_daftar()
    assert "certificate_of_payment_deleted" in sql, sql


@pytest.mark.asyncio
async def test_sambungan_cop_di_daftar_adalah_outer_join():
    """
    Sambungan biasa membuat SELURUH pembelian yang belum tertaut CoP hilang
    dari daftar — dan itu mayoritasnya. Kerusakan seperti ini tidak melempar
    galat apa pun: daftarnya hanya menjadi pendek.
    """
    sql, _ = await _kueri_daftar()
    s = sql.lower()
    assert (
        "left outer join certificate_of_payments" in s
        or "left join certificate_of_payments" in s
    ), sql
