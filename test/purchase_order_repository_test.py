"""
Pengujian `_normalize_row` — fungsi murni yang mengubah baris hasil kueri
menjadi dict biasa dan mengurai kolom JSON.

Pengujian untuk baris item ada di purchase_order_item_repository_test.py.
"""

import json

from repository.purchase_order_repository import _normalize_row


class TestNormalizeRow:
    """`_normalize_row` mengubah baris DB menjadi dict biasa."""

    def test_kolom_json_berbentuk_teks_diurai(self):
        row = _normalize_row(
            {
                "id": 1,
                "customData": json.dumps({"paymentTerm": "CASH"}),
                "billing_requirements": json.dumps({}),
            }
        )
        assert row["customData"] == {"paymentTerm": "CASH"}
        assert row["billing_requirements"] == {}

    def test_kolom_json_yang_sudah_dict_dibiarkan(self):
        row = _normalize_row({"id": 1, "customData": {"paymentTerm": "CR"}})
        assert row["customData"] == {"paymentTerm": "CR"}

    def test_json_rusak_tidak_menggagalkan(self):
        """Data lama bisa saja tidak berbentuk JSON; jangan sampai error."""
        row = _normalize_row({"id": 1, "customData": "bukan json"})
        assert row["customData"] == "bukan json"

    def test_baris_kosong(self):
        assert _normalize_row(None) is None
