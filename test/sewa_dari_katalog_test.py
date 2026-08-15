"""
Baris sewa (PO-B) dapat merujuk alat sewa MAUPUN barang katalog.

Yang disewa tidak selalu alat berat: kadang genset kecil, scaffolding, atau
perlengkapan yang memang terdaftar sebagai barang.

Keduanya disimpan pada KOLOM MASING-MASING, bukan digabung menjadi satu kolom
bertipe. Laporan yang menelusuri pemakaian alat membaca `equipment_id`;
menaruh id barang di sana membuat alat yang tidak pernah ada muncul di
laporannya.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _clean_item():
    s = open(
        os.path.join(AKAR, "repository", "purchase_order_item_repository.py")
    ).read()
    i = s.index("_COLUMNS")
    j = s.index("class PurchaseOrderItemRepository")
    ns = {}
    exec(s[i:j], ns)
    return ns["_clean_item"]


def test_kedua_kolom_nullable():
    """
    Keduanya boleh kosong sendiri-sendiri; yang tidak boleh adalah kosong
    berdua — dan itu dijaga di formulir, bukan di skema.
    """
    s = open(os.path.join(AKAR, "models", "purchase_order_item_model.py")).read()
    for k in ("item_id", "equipment_id"):
        m = re.search(r'''Column\(\s*["']''' + k + r'''["']([^\n]*)''', s)
        assert m, f"kolom {k} tidak ada"
        assert "nullable=True" in m.group(1), f"{k} harus nullable"


def test_baris_dari_alat_sewa():
    bersih = _clean_item()
    r = bersih(
        {"equipment_id": 14, "item_id": None, "quantity": 1, "price": 4500000,
         "unit": "bulan", "remarks_4": "1250000", "remarks_5": "1250000"},
        104,
    )
    assert r["equipment_id"] == 14
    assert r["item_id"] is None
    assert r["remarks_4"] == "1250000"


def test_baris_dari_katalog_barang():
    """
    `task` DIKOSONGKAN untuk barang katalog.

    Namanya sudah ada pada master_item dan diambil lewat join saat dibaca.
    Menyalinnya berarti dokumen menyimpan nama yang dapat berbeda dari
    katalognya bila katalog itu diperbaiki.
    """
    bersih = _clean_item()
    r = bersih(
        {"equipment_id": None, "item_id": 1696, "task": "Beton",
         "quantity": 2, "price": 350000, "unit": "hari"},
        104,
    )
    assert r["item_id"] == 1696
    assert r["equipment_id"] is None
    assert r["task"] is None


def test_pembacaan_menggabungkan_kedua_sumber():
    """
    Dokumen harus terbaca utuh apa pun sumber barisnya — satu join yang
    tertinggal membuat separuh baris kehilangan namanya.
    """
    s = open(
        os.path.join(AKAR, "repository", "purchase_order_item_repository.py")
    ).read()
    i = s.index("async def get_by_po")
    j = s.find("async def ", i + 10)
    b = s[i:] if j == -1 else s[i:j]
    assert "master_item_table" in b
    assert "master_equipment_table" in b


def test_rekap_membaca_kedua_sumber():
    s = open(
        os.path.join(AKAR, "repository", "purchase_order_repository.py")
    ).read()
    i = s.index("async def rekap_proyek")
    j = s.index("async def ", i + 10)
    b = s[i:j]
    assert "itemDescription" in b
    assert "equipmentName" in b
