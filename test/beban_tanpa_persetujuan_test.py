"""
Beban TIDAK punya tahap persetujuan — dan sistemnya harus sejujur itu.

`PUT /expenses/{id}/approve` dulu terdaftar, dijaga izin `expenses:approve`,
dan tidak pernah dapat berhasil: ia menulis tiga kolom yang tidak ada di
tabelnya. Dibuang. Uji ini menjaga agar ia tidak kembali setengah jadi, dan
agar matriks izin tidak lagi menawarkan izin yang tidak menjaga apa pun.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _baca(*jalur):
    return open(os.path.join(AKAR, *jalur), encoding="utf-8").read()


def test_rute_approve_beban_tidak_ada():
    s = _baca("routes", "expenses_routes.py")
    assert '@router.put("/{expense_id}/approve")' not in s


def test_matriks_tidak_menawarkan_persetujuan_beban():
    from constants.permission_matrix import MATRIX

    # (read, create, update, delete, approve) — approve 0 berarti "tidak ada".
    assert MATRIX["expenses"][4] == 0


def test_kolom_persetujuan_memang_tidak_ada_di_tabel():
    """Bila kolomnya kelak ditambahkan, uji ini yang pertama memberi tahu
    bahwa persetujuan beban dapat dibangun — lengkap, bukan dihidupkan dari
    sisa rute lama."""
    from models.expense_model import expenses_table

    for kolom in ("isApprove", "approvedBy", "approvedAt"):
        assert kolom not in expenses_table.c, kolom
