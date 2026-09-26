"""
Pengujian repository item purchase order.

Baris item adalah bagian yang paling sering bermasalah: pernah tidak pernah
tersimpan sama sekali, dan pernah salah kolom (item_id vs equipment_id).
"""

import pytest

from repository.purchase_order_item_repository import (
    PurchaseOrderItemRepository,
    _clean_item,
)

MODULE = "repository.purchase_order_item_repository"


class TestCleanItem:
    """`_clean_item` menyiapkan satu baris purchase_order_items."""

    def test_barang_katalog_memakai_item_id(self):
        row = _clean_item(
            {"item_id": 5, "quantity": 24, "unit": "set", "price": 115_500}, 7
        )
        assert row["purchaseOrderID"] == 7
        assert row["item_id"] == 5
        assert row["equipment_id"] is None

    def test_alat_sewa_memakai_equipment_id(self):
        """PO-B merujuk master_equipment, bukan master_item."""
        row = _clean_item({"equipment_id": 12, "quantity": 30, "unit": "hari"}, 9)
        assert row["equipment_id"] == 12
        assert row["item_id"] is None

    def test_dua_kolom_tidak_saling_menimpa(self):
        row = _clean_item({"item_id": 5, "equipment_id": 12}, 1)
        assert row["item_id"] == 5
        assert row["equipment_id"] == 12

    def test_kolom_wajib_punya_nilai_cadangan(self):
        """quantity/price/unit NOT NULL — nilai kosong harus jadi 0 dan ''."""
        row = _clean_item({"item_id": 5}, 1)
        assert row["quantity"] == 0
        assert row["price"] == 0
        assert row["unit"] == ""

    def test_field_asing_tidak_ikut_tersimpan(self):
        """Form mengirim sku/description yang bukan kolom tabel."""
        row = _clean_item({"item_id": 5, "sku": "LB32", "description": "Jas"}, 1)
        assert "sku" not in row
        assert "description" not in row

    def test_masukan_tidak_diubah(self):
        item = {"item_id": 5}
        _clean_item(item, 1)
        assert item == {"item_id": 5}


class TestInsertMany:
    @pytest.mark.asyncio
    async def test_setiap_item_menghasilkan_satu_insert(self, fake_db):
        db = fake_db(MODULE)
        jumlah = await PurchaseOrderItemRepository.insert_many(
            7,
            [
                {"item_id": 5, "quantity": 24, "unit": "set", "price": 115_500},
                {"item_id": 9, "quantity": 5, "unit": "pcs", "price": 34_000},
            ],
        )
        assert jumlah == 2
        assert db.executed("execute") == 2

    @pytest.mark.asyncio
    async def test_daftar_kosong_tidak_menjalankan_kueri(self, fake_db):
        db = fake_db(MODULE)
        assert await PurchaseOrderItemRepository.insert_many(7, []) == 0
        assert db.executed("execute") == 0

    @pytest.mark.asyncio
    async def test_galat_dilempar_agar_terlihat(self, fake_db):
        """
        Kegagalan menyimpan item harus terlihat oleh controller. Bila ditelan
        diam-diam, PO tersimpan tanpa barang dan baru ketahuan saat dicetak.
        """
        fake_db(MODULE).fail("execute", RuntimeError("kolom tidak dikenal"))
        with pytest.raises(Exception):
            await PurchaseOrderItemRepository.insert_many(7, [{"item_id": 5}])


class TestGetByPo:
    @pytest.mark.asyncio
    async def test_mengembalikan_daftar_dict(self, fake_db):
        fake_db(MODULE).queue(
            "fetch_all",
            [{"id": 1, "item_id": 5, "item_description": "Jas Hujan"}],
        )
        rows = await PurchaseOrderItemRepository.get_by_po(7)
        assert isinstance(rows, list)
        assert rows[0]["item_description"] == "Jas Hujan"

    @pytest.mark.asyncio
    async def test_galat_mengembalikan_daftar_kosong(self, fake_db):
        """Dokumen tetap bisa dibuka walau item gagal diambil."""
        fake_db(MODULE).fail("fetch_all", RuntimeError("join gagal"))
        assert await PurchaseOrderItemRepository.get_by_po(7) == []
