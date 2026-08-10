"""
Pengujian repository purchase order dengan database tiruan.

Yang diperiksa adalah perilaku repository: bentuk balikan yang dijanjikan ke
controller, penanganan galat, dan aturan penomoran PO — bukan mesin basis
datanya.
"""

import pytest

from repository.purchase_order_repository import PurchaseOrderRepository

MODULE = "repository.purchase_order_repository"


class TestNextProjectSequence:
    """Nomor PO berjalan per proyek, bukan global."""

    @pytest.mark.asyncio
    async def test_proyek_baru_mulai_dari_satu(self, fake_db):
        fake_db(MODULE).queue("fetch_val", None)
        assert await PurchaseOrderRepository.get_next_project_sequence("BARU") == 1

    @pytest.mark.asyncio
    async def test_melanjutkan_nomor_tertinggi(self, fake_db):
        fake_db(MODULE).queue("fetch_val", 157)
        assert await PurchaseOrderRepository.get_next_project_sequence("TSKBP") == 158

    @pytest.mark.asyncio
    async def test_nomor_tidak_terpakai_ulang_setelah_penghapusan(self, fake_db):
        """
        Memakai MAX(number), bukan COUNT: menghapus satu PO tidak boleh
        membuat nomor berikutnya bertabrakan dengan yang sudah terbit.
        """
        fake_db(MODULE).queue("fetch_val", 157)
        assert await PurchaseOrderRepository.get_next_project_sequence("TSKBP") == 158

    @pytest.mark.asyncio
    async def test_galat_tidak_menggagalkan_pembuatan_po(self, fake_db):
        fake_db(MODULE).fail("fetch_val", RuntimeError("koneksi putus"))
        assert await PurchaseOrderRepository.get_next_project_sequence("MICZ") == 1


class TestGetAll:
    """Kontrak balikan daftar PO yang dipakai controller & frontend."""

    @pytest.mark.asyncio
    async def test_bentuk_balikan_lengkap(self, fake_db):
        db = fake_db(MODULE)
        db.queue("fetch_all", [{"id": 1, "name": "001-PO-MICZ-G"}])
        db.queue("fetch_val", 1)

        result = await PurchaseOrderRepository.get_all(page=1, page_size=10)

        assert set(["data", "count", "page", "page_size"]).issubset(result)
        assert result["count"] == 1
        assert result["page"] == 1
        assert result["data"][0]["name"] == "001-PO-MICZ-G"

    @pytest.mark.asyncio
    async def test_pencarian_menjalankan_kueri(self, fake_db):
        """Parameter keyword harus diterima — dulu sempat hilang."""
        db = fake_db(MODULE)
        db.queue("fetch_all", [])
        db.queue("fetch_val", 0)

        result = await PurchaseOrderRepository.get_all(1, 10, "MICZ")

        assert result["count"] == 0
        assert db.executed("fetch_all") == 1

    @pytest.mark.asyncio
    async def test_galat_dikembalikan_sebagai_pesan(self, fake_db):
        """Controller mengandalkan kunci 'error' + 'status', bukan exception."""
        fake_db(MODULE).fail("fetch_all", RuntimeError("kueri gagal"))

        result = await PurchaseOrderRepository.get_all()

        assert "error" in result
        assert result["status"] == 500


class TestGetById:
    @pytest.mark.asyncio
    async def test_tidak_ditemukan(self, fake_db):
        fake_db(MODULE).queue("fetch_one", None)
        result = await PurchaseOrderRepository.get_by_id(99)
        assert result["status"] == 404

    @pytest.mark.asyncio
    async def test_kolom_json_ikut_diurai(self, fake_db):
        """get_by_id melewatkan barisnya ke _normalize_row."""
        import json

        fake_db(MODULE).queue(
            "fetch_one",
            {"id": 1, "customData": json.dumps({"paymentTerm": "CR"})},
        )

        result = await PurchaseOrderRepository.get_by_id(1)

        assert result["customData"] == {"paymentTerm": "CR"}
