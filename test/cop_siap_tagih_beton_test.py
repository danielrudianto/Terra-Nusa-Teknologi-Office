"""
Membuat pembelian dari CoP: "CoP ini tidak dapat ditagihkan" padahal belum
ada pembelian sama sekali (22 Sep 2026).

Dua sebab:
  * `siap_tagih` tidak memilih `po.customData`, padahal `melayani_cop`
    membacanya — PO-F beton (materialType di customData) disaring keluar;
  * formulir mencari CoP-nya di 30 baris terbaru saja; sekarang dengan `id`.
"""

from unittest.mock import patch

import pytest

from controllers.certificate_of_payment_controller import (
    CertificateOfPaymentController as C,
)
from repository.certificate_of_payment_repository import (
    CertificateOfPaymentRepository as R,
)


class _Tangkap:
    def __init__(self, baris):
        self.sql = []
        self.nilai = []
        self.baris = baris

    async def __call__(self, sql, nilai=None):
        self.sql.append(" ".join(str(sql).split()))
        self.nilai.append(dict(nilai or {}))
        return self.baris


@pytest.mark.asyncio
async def test_kueri_memilih_customdata_dan_menyaring_id():
    t = _Tangkap([])
    with patch("repository.certificate_of_payment_repository.database.fetch_all", t):
        await R.siap_tagih(cop_id=77)
    assert "po.customData" in t.sql[0], "melayani_cop butuh customData"
    assert "c.id = :cop" in t.sql[0]
    assert t.nilai[0]["cop"] == 77


@pytest.mark.asyncio
async def test_cop_beton_po_f_tetap_siap_tagih():
    beton = {
        "id": 5, "name": "14-COP-R501", "number": 14, "projectName": "R501",
        "date": "2026-09-20", "periodStart": None, "periodEnd": None,
        "netAmount": 1000, "purchaseOrderID": 9, "purchaseOrderName": "PO",
        "purchaseType": "F", "ppn": 11, "pphCode": None, "pphTaxObject": None,
        "pphPercentage": 0, "supplierID": 1,
        "customData": '{"materialType": "beton"}',
        "supplierName": "Adhimix", "supplierAddress": "",
    }

    async def _repo(*a, **k):
        return [beton]

    with patch.object(R, "siap_tagih", _repo):
        hasil = await C.siap_tagih(None, 5, cop_id=5)
    assert [h["id"] for h in hasil] == [5]
