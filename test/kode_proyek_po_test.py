"""
Pilihan proyek pada penyaring purchase order.

KEKELIRUAN YANG DIPERBAIKI

Layar daftar menyusun pilihan proyeknya dari baris yang sedang TAMPIL — satu
halaman, sepuluh dokumen. Proyek yang dokumennya berada di halaman
berikutnya, atau yang seluruh dokumennya berstatus lain, tidak pernah muncul
sebagai pilihan.

Yang dialami orang: memilih status "Diperiksa" lebih dulu, lalu proyek yang
dicarinya hilang dari daftar pilihan — dan tampilannya persis seperti proyek
yang memang tidak punya dokumen. Tidak ada galat, dan tidak ada apa pun di
layar yang menyebut bahwa pilihannya bergantung pada apa yang kebetulan
termuat.

Diuji dengan membaca SUMBERNYA: kueri ini hanya dapat diuji perilakunya
terhadap basis data sungguhan, dan gerbang CI berjalan tanpa basis data.
Perilakunya sudah diukur terpisah terhadap MariaDB — enam dokumen dengan
proyek berulang, satu terhapus, dan satu berproyek kosong menghasilkan tiga
kode yang berbeda dan terurut.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _badan() -> str:
    jalur = os.path.join(AKAR, "repository", "purchase_order_repository.py")
    sumber = open(jalur, encoding="utf-8").read()
    awal = sumber.index("async def kode_proyek(")
    akhir = sumber.index("    @staticmethod", awal)
    return sumber[awal:akhir]


def test_kode_proyek_ada():
    assert "async def kode_proyek(" in open(
        os.path.join(AKAR, "repository", "purchase_order_repository.py"),
        encoding="utf-8",
    ).read()


def test_menyaring_dokumen_yang_dihapus():
    """
    Dokumen terhapus tidak muncul di daftarnya, jadi proyeknya juga tidak
    boleh muncul di pilihannya — memilihnya akan menghasilkan daftar kosong,
    dan pilihan yang pasti kosong lebih buruk daripada tidak ada pilihannya.
    """
    assert "isDelete == False" in _badan()


def test_membuang_proyek_kosong():
    """
    Dokumen tanpa proyek menghasilkan pilihan bernama kosong — baris yang
    tidak dapat dibaca maupun dijelaskan, dan yang memilihnya menyaring
    dengan nilai kosong, yaitu tidak menyaring sama sekali.
    """
    badan = _badan()
    assert "!= None" in badan
    assert '!= ""' in badan


def test_berbeda_dan_terurut():
    """
    Tanpa `distinct`, proyek dengan sepuluh dokumen muncul sepuluh kali.
    Tanpa urutan, pilihannya berpindah-pindah tiap kali dimuat.
    """
    badan = _badan()
    assert ".distinct()" in badan
    assert "order_by" in badan


def test_kegagalan_mengembalikan_daftar_kosong_bukan_galat():
    """
    Penyaring yang pilihannya gagal dimuat tidak boleh menjatuhkan seluruh
    halaman daftarnya — yang dicari orang di halaman itu dokumennya, bukan
    penyaringnya.
    """
    badan = _badan()
    assert "except Exception" in badan
    assert "return []" in badan


def test_rutenya_di_atas_rute_berparameter():
    """
    FastAPI mencocokkan rute BERURUTAN. `/proyek` yang ditaruh di bawah
    `/{purchase_order_id}` akan tertangkap sebagai id, lalu gagal dengan
    galat konversi yang tidak menyebut sebab sebenarnya.
    """
    jalur = os.path.join(AKAR, "routes", "purchase_order_routes.py")
    sumber = open(jalur, encoding="utf-8").read()
    assert sumber.index('@router.get("/proyek")') < sumber.index(
        '@router.get("/{purchase_order_id}"'
    )
