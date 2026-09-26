"""
Barang favorit pada pemilih barang.

Katalognya seribu baris lebih; yang benar-benar dipakai sehari-hari jauh
lebih sedikit. Tanpa penanda ini, barang yang sama dicari ulang setiap kali,
dan yang tidak menemukannya membuat entri kembar.

Yang dijaga di sini: favorit HANYA memengaruhi pemilih, tidak daftar Master
Barang. Di daftar itu yang dicari justru barang yang jarang dipakai, dan
mendorong favorit ke atas membuat sisanya lebih sulit ditemukan.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _baca(*bagian: str) -> str:
    return open(os.path.join(AKAR, *bagian)).read()


def test_kolom_ada_di_model():
    s = _baca("models", "master_item_model.py")
    assert re.search(r'Column\(\s*"isFavorite"\s*,\s*Boolean', s)
    assert 'server_default="0"' in s


def test_tidak_berlaku_secara_bawaan():
    """
    Harus diminta secara sengaja.

    Bila berlaku diam-diam, daftar Master Barang ikut berubah urutannya tanpa
    ada yang memintanya.
    """
    s = _baca("repository", "master_item_repository.py")
    assert "favorit_dulu: bool = False" in s
    r = _baca("routes", "master_item_routes.py")
    assert "favoritDulu: bool = Query(\n        False," in r


def test_favorit_menjadi_kunci_urut_pertama():
    """
    Favorit mendahului, tetapi urutan pilihan pengguna tetap berlaku di dalam
    tiap kelompok — bukan menggantikannya.
    """
    s = _baca("repository", "master_item_repository.py")
    assert "master_item_table.c.isFavorite.desc(), order_by" in s
    assert "order_by(*order_by)" in s


def test_terindeks_di_meilisearch():
    """
    Urutan pada pemilih dibaca dari indeks; tanpa kolomnya di sana,
    penandaannya tersimpan tetapi tidak mengubah apa pun yang terlihat.
    """
    s = _baca("utils", "meilisearch_item.py")
    assert '"isFavorite": bool(' in s
    assert re.search(r'"sortableAttributes":[^\]]*"isFavorite"', s)


def test_indeks_disegarkan_saat_ditandai():
    s = _baca("controllers", "master_item_controller.py")
    i = s.index("async def set_favorite")
    j = s.index("async def ", i + 10)
    assert "index_document(" in s[i:j]


def test_kegagalan_indeks_tidak_membatalkan_penandaan():
    """
    Penandaannya sudah tersimpan di basis data; membatalkannya karena indeks
    gagal berarti kehilangan pekerjaan yang sudah benar.
    """
    s = _baca("controllers", "master_item_controller.py")
    i = s.index("async def set_favorite")
    j = s.index("async def ", i + 10)
    blok = s[i:j]
    assert "try:" in blok and "except Exception" in blok
    assert blok.index("index_document(") > blok.index("try:")


def test_menandai_butuh_izin_update():
    """
    Bukan preferensi pribadi: urutannya berlaku untuk SELURUH pengguna, jadi
    izinnya sama dengan menyunting barangnya.
    """
    s = _baca("routes", "master_item_routes.py")
    i = s.index('@router.patch("/{item_id}/favorite")')
    j = s.index("@router.", i + 10)
    assert 'require("master_item", "update")' in s[i:j]
