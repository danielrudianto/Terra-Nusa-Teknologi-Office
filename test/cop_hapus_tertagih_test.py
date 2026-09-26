"""
CoP yang SUDAH DITAGIHKAN tidak dapat dihapus.

Penjagaan penghapusan sebelumnya hanya menimbang level pengguna, tidak
pernah menimbang apakah tagihannya benar-benar ada. Satu klik dari daftar
dapat menghapus CoP yang pembeliannya masih hidup, dan yang tertinggal:
pembelian yang tetap dapat dibayar, tetap masuk biaya proyek dan masa
pajak, serta volume yang dapat disertifikasi ULANG karena akumulasi "CoP
sebelumnya" menyaring yang terhapus.

Sisi pembelian sudah menjaga dirinya begini. Sisi sertifikasi tidak.
"""
from unittest.mock import AsyncMock, patch

import pytest

from controllers.certificate_of_payment_controller import (
    CertificateOfPaymentController as Ctl,
)
from repository.certificate_of_payment_repository import (
    CertificateOfPaymentRepository as Repo,
)


COP = {"id": 214, "isApproved": 1, "createdBy": 9, "name": "007-SPK-R501-D/CoP-003"}
TAGIHAN = {"id": 55, "invoiceName": "16-968-INV-R501-IX-2026"}


@pytest.mark.asyncio
async def test_cop_yang_sudah_ditagihkan_tidak_dapat_dihapus():
    with patch.object(Repo, "get_by_id", AsyncMock(return_value=dict(COP))), \
         patch.object(Repo, "tagihan", AsyncMock(return_value=dict(TAGIHAN))), \
         patch.object(Repo, "soft_delete", AsyncMock()) as hapus:
        hasil = await Ctl.delete(214, user_id=9, user_level=5)
    assert hasil["status"] == 409
    assert not hapus.called


@pytest.mark.asyncio
async def test_pesannya_menyebut_nomor_invoice_yang_menghalangi():
    """
    "Tidak dapat dihapus" tanpa menyebut apa yang menghalangi membuat orang
    mencari sendiri — dan nomor invoice-nya justru sudah ada di tangan.
    """
    with patch.object(Repo, "get_by_id", AsyncMock(return_value=dict(COP))), \
         patch.object(Repo, "tagihan", AsyncMock(return_value=dict(TAGIHAN))), \
         patch.object(Repo, "soft_delete", AsyncMock()):
        hasil = await Ctl.delete(214, user_id=9, user_level=5)
    assert "16-968-INV-R501-IX-2026" in str(hasil)


@pytest.mark.asyncio
async def test_level_tertinggi_pun_tidak_boleh_menembusnya():
    """
    Penjagaan ini soal KEADAAN dokumen, bukan wewenang. Level 5 yang
    menghapus CoP bertagihan meninggalkan kerusakan yang sama persis.
    """
    with patch.object(Repo, "get_by_id", AsyncMock(return_value=dict(COP))), \
         patch.object(Repo, "tagihan", AsyncMock(return_value=dict(TAGIHAN))), \
         patch.object(Repo, "soft_delete", AsyncMock()) as hapus:
        hasil = await Ctl.delete(214, user_id=1, user_level=5)
    assert hasil["status"] == 409 and not hapus.called


@pytest.mark.asyncio
async def test_yang_pembeliannya_sudah_dibatalkan_tetap_dapat_dihapus():
    """
    `Repo.tagihan` menyaring pembelian yang sudah dihapus, sehingga CoP yang
    tagihannya SUDAH dibatalkan kembali dapat dihapus — dan itu memang
    keadaan yang seharusnya boleh.
    """
    with patch.object(Repo, "get_by_id", AsyncMock(return_value=dict(COP))), \
         patch.object(Repo, "tagihan", AsyncMock(return_value=None)), \
         patch.object(Repo, "soft_delete", AsyncMock(return_value={"message": "ok"})) as hapus:
        hasil = await Ctl.delete(214, user_id=9, user_level=5)
    assert hapus.called and "status" not in hasil


@pytest.mark.asyncio
async def test_penjagaan_level_tetap_berlaku_lebih_dahulu():
    """Yang belum berwenang ditolak 403, bukan 409 — dan tanpa menyentuh DB."""
    with patch.object(Repo, "get_by_id", AsyncMock(return_value=dict(COP))), \
         patch.object(Repo, "tagihan", AsyncMock(return_value=None)) as baca, \
         patch.object(Repo, "soft_delete", AsyncMock()) as hapus:
        hasil = await Ctl.delete(214, user_id=1, user_level=2)
    assert hasil["status"] == 403 and not hapus.called and not baca.called
