"""Tender BARANG: baris wajib dari katalog; tender JASA bebas."""
from unittest.mock import AsyncMock, patch

import pytest

import controllers.tender_controller as tc


@pytest.mark.asyncio
async def test_jasa_bebas():
    assert await tc.periksa_baris_barang("jasa", [{"name": "Galian"}]) is None


@pytest.mark.asyncio
async def test_items_tidak_disebut_tidak_diperiksa():
    assert await tc.periksa_baris_barang("barang", None) is None


@pytest.mark.asyncio
async def test_barang_tanpa_item_id_ditolak():
    g = await tc.periksa_baris_barang(
        "barang", [{"itemID": 3, "name": "a"}, {"itemID": None, "name": "Semen"}]
    )
    assert g["status"] == 422 and "baris 2" in g["error"]


@pytest.mark.asyncio
async def test_barang_terhapus_ditolak():
    with patch.object(tc.database, "fetch_all", AsyncMock(return_value=[{"id": 3}])):
        g = await tc.periksa_baris_barang("barang", [{"itemID": 3}, {"itemID": 9}])
    assert g["status"] == 422


@pytest.mark.asyncio
async def test_barang_katalog_lolos():
    with patch.object(tc.database, "fetch_all", AsyncMock(return_value=[{"id": 3}, {"id": 9}])):
        assert await tc.periksa_baris_barang("barang", [{"itemID": 3}, {"itemID": 9}]) is None


@pytest.mark.asyncio
async def test_ubah_memakai_jenis_tersimpan():
    tender = {"id": 1, "status": "draft", "tenderType": "barang"}
    with patch.object(tc.TenderRepository, "ambil", AsyncMock(return_value=tender)), \
         patch.object(tc.TenderRepository, "ubah", AsyncMock(return_value={"ok": 1})) as ubah:
        g = await tc.TenderController.ubah(1, {"items": [{"name": "Bebas"}]}, 7)
        assert g["status"] == 422 and not ubah.called
        # Ganti nama saja (tanpa items) tetap boleh — tender lama tidak terkunci.
        assert await tc.TenderController.ubah(1, {"name": "Baru"}, 7) == {"ok": 1}
