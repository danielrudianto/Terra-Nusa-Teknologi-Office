"""
Pengujian skema purchase order.

Skema di FastAPI berperan sebagai penyaring: field yang tidak dideklarasikan
akan dibuang diam-diam, baik pada permintaan masuk maupun respons keluar.
Kelalaian semacam itu tidak memunculkan error — hanya datanya yang hilang —
sehingga justru perlu dijaga dengan pengujian.
"""

import pytest

from schemas.purchase_order_schema import (
    PurchaseOrderCreate,
    PurchaseOrderResponse,
)


def _base_payload(**extra):
    payload = {
        "date": "2026-08-08",
        "supplierID": 1,
        "purchaseType": "G",
        "templateVersion": "1.0",
        "projectName": "MICZ",
        "dpp": 2_942_000,
        "ppn": 11,
        "billing_requirements": {},
    }
    payload.update(extra)
    return payload


class TestPurchaseOrderCreate:
    def test_items_ikut_terkirim_ke_controller(self):
        """Tanpa field `items`, seluruh baris barang hilang sebelum disimpan."""
        payload = _base_payload(
            items=[
                {"item_id": 5, "quantity": 24, "unit": "set", "price": 115_500},
                {"item_id": 9, "quantity": 5, "unit": "pcs", "price": 34_000},
            ]
        )

        data = PurchaseOrderCreate(**payload).model_dump()

        assert data["items"] is not None
        assert len(data["items"]) == 2
        assert data["items"][0]["item_id"] == 5
        assert data["items"][0]["quantity"] == 24

    def test_items_boleh_kosong(self):
        """PO tanpa barang tetap sah; jangan sampai wajib diisi."""
        data = PurchaseOrderCreate(**_base_payload()).model_dump()
        assert data["items"] is None

    def test_project_code_diterima(self):
        """projectCode hanya penolong penomoran, bukan kolom tabel."""
        data = PurchaseOrderCreate(**_base_payload(projectCode="MICZ")).model_dump()
        assert data["projectCode"] == "MICZ"

    @pytest.mark.parametrize("field", ["supplierID", "projectName", "purchaseType"])
    def test_field_wajib_tidak_boleh_hilang(self, field):
        payload = _base_payload()
        payload.pop(field)
        with pytest.raises(Exception):
            PurchaseOrderCreate(**payload)


class TestPurchaseOrderResponse:
    def _response(self, **extra):
        payload = {
            "id": 7,
            "date": "2026-08-08",
            "supplierID": 1,
            "name": "001-PO-MICZ-G",
            "purchaseType": "G",
            "templateVersion": "1.0",
            "projectName": "MICZ",
            "dpp": 2_942_000,
            "ppn": 11,
        }
        payload.update(extra)
        return PurchaseOrderResponse(**payload).model_dump()

    def test_items_ikut_pada_respons(self):
        """Dipakai saat mencetak ulang; tanpa ini tabel barang kosong."""
        data = self._response(
            items=[{"item_id": 5, "quantity": 24, "unit": "set", "price": 115_500}]
        )
        assert data["items"] and data["items"][0]["item_id"] == 5

    def test_identitas_supplier_ikut_pada_respons(self):
        data = self._response(
            supplierName="Alfa Bangunan",
            supplierPrefix="UD.",
            supplierAddress="Ruko Citra Raya Blok D1 No. 12 R",
            supplierCity="Tangerang, Banten",
            supplierNpwp="0427485883421000",
        )
        assert data["supplierName"] == "Alfa Bangunan"
        assert data["supplierPrefix"] == "UD."
        assert data["supplierCity"] == "Tangerang, Banten"
        assert data["supplierNpwp"] == "0427485883421000"

    def test_nomor_urut_per_proyek_ikut(self):
        assert self._response(number=4)["number"] == 4

    def test_supplier_pada_daftar_ikut(self):
        """Kolom hasil join pada daftar PO memakai penamaan snake_case."""
        data = self._response(
            supplier_name="Alfa Bangunan", supplier_prefix="UD."
        )
        assert data["supplier_name"] == "Alfa Bangunan"
        assert data["supplier_prefix"] == "UD."
