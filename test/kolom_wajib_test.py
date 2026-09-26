"""
Kolom NOT NULL harus diisi EKSPLISIT saat insert.

`default=` pada definisi kolom dievaluasi mesin SQLAlchemy saat eksekusi.
Pustaka `databases` menjalankan kueri yang sudah dikompilasi, sehingga
langkah itu DILEWATI dan nilainya sampai ke MySQL sebagai NULL — lalu
ditolak oleh `NOT NULL`.

`server_default` pun tidak menolong bila kolomnya ikut disebut dalam kueri
dengan nilai NULL; ia hanya berlaku ketika kolomnya tidak disebut sama
sekali.

Sudah menjatuhkan pembuatan barang master: `Column('isFavorite', Boolean,
nullable=False, server_default="0", default=False)` menghasilkan
`(1048, "Column 'isFavorite' cannot be null")` pada setiap barang baru.

Pola yang benar sudah dipakai dua puluh dua tempat yang mengisi `createdAt`
manual, dengan alasan yang sama persis.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_isfavorite_diisi_eksplisit():
    s = open(os.path.join(AKAR, "repository", "master_item_repository.py")).read()
    i = s.index("async def create(")
    j = s.index("async def ", i + 10)
    blok = s[i:j]
    assert "insert(master_item_table)" in blok
    assert "isFavorite=False" in blok, (
        "isFavorite harus diisi eksplisit; default kolom tidak berlaku "
        "dengan pustaka `databases`"
    )


def test_kolom_baru_sesi_ini_aman():
    """
    Kolom lain yang ditambahkan belakangan bersifat NULLABLE.

    Kolom nullable tidak memerlukan pengisian eksplisit. Uji ini menjaga agar
    tidak ada yang mengubahnya menjadi NOT NULL tanpa sekaligus mengisinya di
    setiap insert — perubahan yang tampak sepele tetapi menjatuhkan seluruh
    pembuatan data pada tabel itu.
    """
    peta = {
        "purchase_order_model.py": ["parentPurchaseOrderID", "addendumNumber"],
        "sales_invoice_model.py": ["separatedInvoice"],
    }
    for berkas, kolom in peta.items():
        s = open(os.path.join(AKAR, "models", berkas)).read()
        for k in kolom:
            m = re.search(r"""Column\(\s*['"]""" + k + r"""['"]([^\n]*)""", s)
            assert m, f"{berkas}: kolom {k} tidak ditemukan"
            assert "nullable=False" not in m.group(1), (
                f"{berkas}.{k} kini NOT NULL — pastikan setiap insert "
                f"mengisinya eksplisit sebelum mengubah uji ini"
            )


def test_pengguna_diisi_aktif_dan_tidak_terhapus():
    """
    `isActive` dan `isDeleted` diisi eksplisit saat membuat pengguna.

    Kolomnya NULLABLE, sehingga penyimpanannya BERHASIL walaupun nilainya
    NULL — dan barulah jawaban rutenya ditolak `response_model` karena NULL
    bukan boolean.

    Akibatnya paling menyesatkan di antara kelas kesalahan ini: penggunanya
    SUDAH TERBUAT, tetapi layar menerima galat 500 dan menyangka gagal, lalu
    mencoba lagi dan membuat pengguna kembar.
    """
    s = open(os.path.join(AKAR, "repository", "user_repository.py")).read()
    i = s.index("insert(users_table)")
    blok = s[max(0, i - 900):i]
    assert 'setdefault("isActive", True)' in blok
    assert 'setdefault("isDeleted", False)' in blok
