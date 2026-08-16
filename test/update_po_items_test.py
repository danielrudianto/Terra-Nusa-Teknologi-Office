"""
Pengubahan purchase order menyimpan barisnya dan menyaring kolomnya.

Formulir mengirim muatan yang sama seperti saat membuat dokumen. Sebagian
isinya bukan kolom tabel — `projectCode` hanya dipakai server untuk menyusun
nomor, dan `items` adalah tabel tersendiri.

Meneruskan keduanya ke `update()` membuat SQLAlchemy menolak SELURUH
permintaan dengan "Unconsumed column names", dan pesan itu tidak menyebut
bahwa yang salah hanya dua kunci di antara enam belas.

Perbaikan ini pernah hilang sekali karena tertimpa merge. Uji ini yang
membuat kehilangan berikutnya terlihat sebelum sampai ke produksi.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERKAS = os.path.join(AKAR, 'repository', 'purchase_order_repository.py')


def _blok(nama: str) -> str:
    s = open(BERKAS).read()
    i = s.index(f'async def {nama}(')
    j = s.find('async def ', i + 10)
    return s[i:] if j == -1 else s[i:j]


def test_items_dipisahkan_dari_kolom():
    b = _blok('update')
    assert 'fields.pop("items"' in b


def test_kunci_bukan_kolom_dibuang():
    """
    Disaring terhadap kolom tabel yang sebenarnya, bukan daftar tetap.

    Daftar tetap akan tertinggal begitu ada kolom baru, dan kolom yang sah
    justru terbuang tanpa ada yang menyadarinya.
    """
    b = _blok('update')
    assert 'purchase_orders_table.columns' in b


def test_baris_barang_disimpan():
    b = _blok('update')
    assert 'delete_by_po' in b
    assert 'insert_many' in b


def test_baris_diganti_seluruhnya():
    """
    Dihapus lalu ditulis ulang, bukan dicocokkan per id.

    Yang mengubah dapat menambah, menghapus, dan menukar urutan sekaligus.
    Dokumen ini belum pernah terbit, sehingga tidak ada yang merujuk id
    barisnya.
    """
    b = _blok('update')
    assert b.index('delete_by_po') < b.index('insert_many')


def test_revisi_tetap_naik():
    b = _blok('update')
    assert 'revision=purchase_orders_table.c.revision + 1' in b
