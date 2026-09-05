"""
Setiap metode repository yang DIPANGGIL controller harus benar-benar ada.

Tiga kekeliruan yang sama persis pernah lolos ke produksi dalam satu pekan:

  * `ExpenseRepository.get_expense_by_id`  — tidak pernah ada (yang ada `get_by_id`)
  * `SalarySlipRepository.get_salary_slip_by_id` — sama
  * `SalarySlipRepository.punya_pembayaran` — ADA di berkasnya, tetapi menempel
    pada kelas TERAKHIR di berkas itu (`SalarySlipDeductionRepository`) karena
    ditambahkan di ujung berkas

Ketiganya berupa `AttributeError` saat dijalankan, dan ketiganya jatuh ke
`except Exception` yang mengubahnya menjadi "Internal server error" — atau,
lebih buruk, ditelan diam-diam sehingga fiturnya tampak berjalan padahal tidak
mengerjakan apa pun.

Diperiksa secara STATIS dengan `ast`: tidak ada modul yang diimpor, tidak ada
basis data yang disentuh, sehingga uji ini tidak dapat gagal karena lingkungan.
"""

import ast
import os
import sys

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _kelas_dalam(direktori):
    """Petakan nama kelas -> himpunan nama metodenya, untuk seluruh berkas."""
    peta = {}
    jalur = os.path.join(AKAR, direktori)
    if not os.path.isdir(jalur):
        return peta
    for nama in os.listdir(jalur):
        if not nama.endswith(".py"):
            continue
        with open(os.path.join(jalur, nama), encoding="utf-8") as f:
            pohon = ast.parse(f.read(), filename=nama)
        for simpul in pohon.body:
            if isinstance(simpul, ast.ClassDef):
                peta[simpul.name] = {
                    m.name
                    for m in simpul.body
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
    return peta


def _panggilan(direktori):
    """Setiap `NamaKelas.metode(...)` pada berkas-berkas di direktori ini."""
    hasil = []
    jalur = os.path.join(AKAR, direktori)
    if not os.path.isdir(jalur):
        return hasil
    for nama in os.listdir(jalur):
        if not nama.endswith(".py"):
            continue
        berkas = os.path.join(jalur, nama)
        with open(berkas, encoding="utf-8") as f:
            pohon = ast.parse(f.read(), filename=nama)
        for simpul in ast.walk(pohon):
            if not isinstance(simpul, ast.Call):
                continue
            fn = simpul.func
            if not isinstance(fn, ast.Attribute):
                continue
            if not isinstance(fn.value, ast.Name):
                continue
            hasil.append((nama, simpul.lineno, fn.value.id, fn.attr))
    return hasil


def test_metode_repository_yang_dipanggil_memang_ada():
    repo = _kelas_dalam("repository")
    assert repo, "tidak ada kelas repository yang terbaca — periksa letak berkas uji"

    salah = []
    for direktori in ("controllers", "routes", "repository"):
        for berkas, baris, kelas, metode in _panggilan(direktori):
            # Hanya kelas yang memang kita kenali; sisanya (pustaka luar,
            # variabel lokal) bukan urusan uji ini.
            if kelas not in repo:
                continue
            if metode in repo[kelas]:
                continue
            # Metode bawaan objek dan yang diwarisi tidak perlu dideklarasikan.
            if hasattr(object, metode):
                continue
            salah.append(f"{direktori}/{berkas}:{baris} -> {kelas}.{metode}")

    assert not salah, "Metode repository yang dipanggil tetapi tidak ada:\n  " + "\n  ".join(
        sorted(salah)
    )


if __name__ == "__main__":
    try:
        test_metode_repository_yang_dipanggil_memang_ada()
    except AssertionError as e:
        print(e)
        sys.exit(1)
    print("lolos — semua metode repository yang dipanggil memang ada")
