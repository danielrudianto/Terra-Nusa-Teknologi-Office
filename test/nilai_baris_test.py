"""
Jumlah baris yang DITULIS, dan batasnya.

Harga satuan tersimpan empat desimal, dan sebagian pekerjaan tidak pernah
bulat pada ketelitian itu: 7.000 liter seharga Rp 300.000 berarti
Rp 42,857142… per liter. Yang paling dekat yang dapat disimpan adalah 42,8571
— menghasilkan Rp 299.999,70 pada dokumen yang ditandatangani. Menambah
desimal tidak menyelesaikannya; pecahannya berulang tanpa habis.

Yang dijaga di sini BATASNYA. Tanpa batas, kolom ini menjadi pintu memasukkan
angka yang tidak ada hubungannya dengan volume dan harganya — dan yang
membacanya mengalikan keduanya, mendapat angka lain, lalu menanyakan mana yang
benar.
"""

from models.purchase_order_item_model import purchase_order_items_table
from repository.purchase_order_item_repository import (
    TOLERANSI_PEMBULATAN,
    _clean_item,
    nilai_baris,
    pembulatan_sah,
)

AIR = {"quantity": 7000, "price": 42.8571}
HITUNG = 7000 * 42.8571  # 299_999.7


def test_kolomnya_ada():
    assert "amount" in {c.name for c in purchase_order_items_table.columns}


def test_tanpa_jumlah_tertulis_dihitung_biasa():
    assert nilai_baris(AIR) == HITUNG


def test_jumlah_tertulis_dipakai():
    assert nilai_baris({**AIR, "amount": 300000}) == 300000


def test_baris_lama_tidak_berubah():
    """
    Penjaga terpenting.

    Seluruh baris yang sudah ada bernilai NULL, dan pencetakan ulangnya harus
    menghasilkan angka yang sama persis dengan lembar yang ditandatangani.
    """
    for kosong in (None, ""):
        assert nilai_baris({**AIR, "amount": kosong}) == HITUNG, kosong


def test_selisih_kecil_diterima():
    assert pembulatan_sah({**AIR, "amount": 300000})


def test_selisih_tepat_di_batas_diterima():
    assert pembulatan_sah({**AIR, "amount": HITUNG + TOLERANSI_PEMBULATAN})
    assert pembulatan_sah({**AIR, "amount": HITUNG - TOLERANSI_PEMBULATAN})


def test_selisih_di_luar_batas_ditolak():
    assert not pembulatan_sah({**AIR, "amount": HITUNG + TOLERANSI_PEMBULATAN + 0.01})
    assert not pembulatan_sah({**AIR, "amount": 500000})


def test_nilai_yang_tidak_terbaca_ditolak():
    # Bukan diterima diam-diam: angka yang tidak terbaca akan tersimpan
    # sebagai sesuatu yang lain.
    assert not pembulatan_sah({**AIR, "amount": "ngawur"})


def test_yang_di_luar_batas_DIBUANG_saat_disimpan():
    """
    Dibuang, bukan menggagalkan penyimpanan.

    Barisnya lalu jatuh ke perkalian biasa — angka yang selalu dapat
    dipertanggungjawabkan.
    """
    row = _clean_item({**AIR, "amount": 500000}, po_id=1)
    assert row["amount"] is None


def test_yang_di_dalam_batas_TERSIMPAN():
    row = _clean_item({**AIR, "amount": 300000}, po_id=1)
    assert float(row["amount"]) == 300000


def test_baris_tanpa_amount_tetap_tersimpan_kosong():
    row = _clean_item(dict(AIR), po_id=1)
    assert row["amount"] is None


def test_amount_untai_kosong_jadi_none_bukan_string():
    """
    Regresi: kolom "Jumlah (opsional)" yang dikosongkan dikirim layar sebagai
    untai KOSONG "", bukan None. Bila diteruskan apa adanya ke kolom Float,
    MySQL menolak ("Incorrect DOUBLE value: ''") dan seluruh penyimpanan baris
    gagal — persis kegagalan pada PO-C. Harus menjadi None, bukan "".
    """
    row = _clean_item({**AIR, "amount": ""}, po_id=1)
    assert row["amount"] is None
    # angka lain pun tidak boleh tersisa sebagai untai
    assert not isinstance(row["quantity"], str)
    assert not isinstance(row["price"], str)


def test_amount_untai_berangka_terbaca():
    """Untai angka dari mask (mis. '300000', '300 000') terbaca sebagai angka."""
    assert _clean_item({**AIR, "amount": "300000"}, po_id=1)["amount"] == 300000
    assert _clean_item({**AIR, "amount": "300 000"}, po_id=1)["amount"] == 300000
