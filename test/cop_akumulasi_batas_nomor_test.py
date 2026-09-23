"""
Kolom "Sebelumnya" dan "Akumulatif" pada BAP DIBATASI NOMOR DOKUMENNYA.

Lembar yang sudah terbit harus tercetak sama selamanya. Bila akumulasinya
menjumlahkan SELURUH CoP yang ada saat dicetak, BAP Agustus yang dicetak
ulang pada September akan memuat volume September — dokumen yang sama
menyebut angka berbeda pada dua hari yang berbeda, dan yang membaca tidak
punya cara tahu mana yang benar.
"""
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

import repository.certificate_of_payment_repository as r
from repository.certificate_of_payment_repository import (
    CertificateOfPaymentRepository as Repo,
)


@pytest.mark.asyncio
async def test_sebelumnya_dibatasi_nomor_dan_mencakup_seluruh_rantai():
    with patch.object(Repo, "rantai_ids", AsyncMock(return_value=[5, 9])), \
         patch.object(r.database, "fetch_all", AsyncMock(return_value=[])) as f:
        await Repo.cop_sebelumnya(5, nomor=3)
    sql, nilai = f.await_args.args[0], f.await_args.args[1]
    # Nomor yang LEBIH BESAR tidak boleh ikut: itu dokumen yang terbit kemudian.
    assert "c.number < :nomor" in sql
    assert nilai["nomor"] == 3
    # Adendum ikut terbaca, sama seperti `riwayat_pembayaran`.
    assert "c.purchaseOrderID IN :ids" in sql
    assert nilai["ids"] == (5, 9)


@pytest.mark.asyncio
async def test_riwayat_berhenti_pada_nomor_ini():
    with patch.object(Repo, "rantai_ids", AsyncMock(return_value=[5])), \
         patch.object(r.database, "fetch_all", AsyncMock(return_value=[])) as f:
        await Repo.riwayat_pembayaran(5, sampai_nomor=2)
    sql, nilai = f.await_args.args[0], f.await_args.args[1]
    assert "number <= :nomor" in sql and nilai["nomor"] == 2


@pytest.mark.asyncio
async def test_dibatalkan_dan_terhapus_tidak_ikut():
    with patch.object(Repo, "rantai_ids", AsyncMock(return_value=[5])), \
         patch.object(r.database, "fetch_all", AsyncMock(return_value=[])) as f:
        await Repo.cop_sebelumnya(5, nomor=9)
    sql = f.await_args.args[0]
    assert "c.isDelete = 0" in sql and "c.status <> 'cancelled'" in sql


@pytest.mark.asyncio
async def test_jumlah_per_baris_dikembalikan_sebagai_decimal():
    with patch.object(Repo, "rantai_ids", AsyncMock(return_value=[5])), \
         patch.object(
             r.database, "fetch_all",
             AsyncMock(return_value=[{"baris": 11, "jumlah": "3.50"}]),
         ):
        hasil = await Repo.cop_sebelumnya(5, nomor=2)
    assert hasil == {11: Decimal("3.50")}
