"""
SPK lama: tarif lembur disepakati, tetapi barisnya tidak ada. Layar CoP harus
MENYEBUTKANNYA, bukan menampilkan daftar volume tanpa lembur begitu saja.
"""
from unittest.mock import AsyncMock, patch

import pytest

import repository.certificate_of_payment_repository as r
from repository.certificate_of_payment_repository import (
    CertificateOfPaymentRepository as Repo,
)


@pytest.mark.asyncio
async def test_tanpa_rantai_tidak_memperingatkan():
    with patch.object(Repo, "rantai_ids", AsyncMock(return_value=[])):
        assert await Repo.lembur_tanpa_baris(1) == {"ada": False}


@pytest.mark.asyncio
async def test_tarif_ada_baris_tidak_ada_diperingatkan():
    baris = {"id": 7, "customData": {"overtimeRate": 50000, "overtimeUnit": "jam"}}
    with patch.object(Repo, "rantai_ids", AsyncMock(return_value=[7])), \
         patch.object(r.database, "fetch_all", AsyncMock(return_value=[])), \
         patch.object(r.database, "fetch_one", AsyncMock(return_value=baris)):
        hasil = await Repo.lembur_tanpa_baris(7)
    assert hasil == {"ada": True, "satuan": "jam"}


@pytest.mark.asyncio
async def test_tarif_nol_bukan_peringatan():
    baris = {"id": 7, "customData": {"overtimeRate": 0, "overtimeUnit": "jam"}}
    with patch.object(Repo, "rantai_ids", AsyncMock(return_value=[7])), \
         patch.object(r.database, "fetch_all", AsyncMock(return_value=[])), \
         patch.object(r.database, "fetch_one", AsyncMock(return_value=baris)):
        assert await Repo.lembur_tanpa_baris(7) == {"ada": False}


@pytest.mark.asyncio
async def test_spk_yang_sudah_punya_baris_lembur_tidak_diperingatkan():
    with patch.object(Repo, "rantai_ids", AsyncMock(return_value=[7])), \
         patch.object(r.database, "fetch_all", AsyncMock(return_value=[{"purchaseOrderID": 7}])), \
         patch.object(r.database, "fetch_one", AsyncMock()) as f:
        assert await Repo.lembur_tanpa_baris(7) == {"ada": False}
    # Tidak perlu membaca dokumennya sama sekali bila barisnya sudah ada.
    assert not f.called


@pytest.mark.asyncio
async def test_peringatan_gagal_tidak_menjatuhkan_layar():
    import controllers.certificate_of_payment_controller as c
    with patch.object(Repo, "lembur_tanpa_baris", AsyncMock(side_effect=RuntimeError("x"))):
        assert await c.CertificateOfPaymentController.peringatan_lembur(1) == {"ada": False}
