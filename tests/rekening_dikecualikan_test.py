"""
Menjaga satu kelas kesalahan, bukan satu kolom.

Rekening bank dibaca dan ditulis di lima tempat yang masing-masing menyebut
kolomnya SATU PER SATU. Kolom yang tidak disebut tidak menimbulkan error di
mana pun — ia hanya hilang. Pydantic membuang bidang yang tidak dideklarasikan
tanpa bersuara, konstruksi BankAccount(...) mengambil default, dan .values()
menulis NULL. Tampilannya tetap bekerja; nilainya saja yang tidak pernah
sampai.

Itulah yang terjadi pada excludeFromCalendar, dan akan terjadi lagi pada kolom
berikutnya. Jadi yang diuji bukan "apakah excludeFromCalendar ada", melainkan
"apakah setiap kolom tabel disebut di setiap tempat yang menyebut kolom".

Seluruh pemeriksaan dilakukan secara statis lewat AST — tidak ada basis data,
tidak ada Redis, tidak ada import aplikasi.
"""

import ast
from pathlib import Path

import pytest

AKAR = Path(__file__).resolve().parents[1]
BERKAS_MODEL = AKAR / "models" / "bank_model.py"
BERKAS_REPO = AKAR / "repository" / "bank_account_repository.py"
BERKAS_CTRL = AKAR / "controllers" / "bank_controller.py"


def _pohon(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def kolom_tabel() -> set[str]:
    """Nama kolom bank_accounts_table, dibaca dari sumbernya."""
    pohon = _pohon(BERKAS_MODEL)
    for simpul in ast.walk(pohon):
        if not isinstance(simpul, ast.Assign):
            continue
        sasaran = [t.id for t in simpul.targets if isinstance(t, ast.Name)]
        if "bank_accounts_table" not in sasaran:
            continue
        nama = set()
        for arg in getattr(simpul.value, "args", []):
            if (
                isinstance(arg, ast.Call)
                and isinstance(arg.func, ast.Name)
                and arg.func.id == "Column"
                and arg.args
                and isinstance(arg.args[0], ast.Constant)
            ):
                nama.add(arg.args[0].value)
        return nama
    pytest.fail("bank_accounts_table tidak ditemukan di models/bank_model.py")


def kelas_bankaccount() -> ast.ClassDef:
    for simpul in _pohon(BERKAS_REPO).body:
        if isinstance(simpul, ast.ClassDef) and simpul.name == "BankAccount":
            return simpul
    pytest.fail("class BankAccount tidak ditemukan di repository")


def test_model_pydantic_menyebut_setiap_kolom_tabel():
    """
    Bidang yang tidak dideklarasikan pada model Pydantic DIBUANG diam-diam,
    baik saat data masuk maupun saat keluar.
    """
    bidang = {
        s.target.id
        for s in kelas_bankaccount().body
        if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
    }
    kurang = kolom_tabel() - bidang
    assert not kurang, (
        f"Kolom tabel yang tidak ada pada model Pydantic BankAccount: "
        f"{sorted(kurang)}. Nilainya akan hilang tanpa error."
    )


def test_create_menulis_setiap_kolom_tabel():
    """insert().values(...) menyebut kolom satu per satu; yang lupa jadi NULL."""
    kelas = kelas_bankaccount()
    disebut: set[str] = set()
    for simpul in ast.walk(kelas):
        if (
            isinstance(simpul, ast.Call)
            and isinstance(simpul.func, ast.Attribute)
            and simpul.func.attr == "values"
        ):
            disebut |= {kw.arg for kw in simpul.keywords if kw.arg}
    assert disebut, "insert().values(...) tidak ditemukan pada BankAccount.create()"

    # id diisi basis data.
    kurang = kolom_tabel() - disebut - {"id"}
    assert not kurang, (
        f"BankAccount.create() tidak menulis kolom: {sorted(kurang)}. "
        f"Rekening baru akan tersimpan tanpa nilai itu."
    )


def test_setiap_konstruksi_bankaccount_menyebut_setiap_kolom():
    """
    Tiga query (get_banks, get_bank_account_by_id, get_bank_accounts_by_ids)
    membangun BankAccount(...) dengan menyebut kolomnya satu per satu.
    Ketiganya harus lengkap — kalau tidak, kolomnya hilang di jalur baca itu
    saja, sehingga bug-nya muncul hanya di sebagian layar.
    """
    kolom = kolom_tabel()
    konstruksi = [
        s
        for s in ast.walk(_pohon(BERKAS_REPO))
        if isinstance(s, ast.Call)
        and isinstance(s.func, ast.Name)
        and s.func.id == "BankAccount"
    ]
    assert len(konstruksi) >= 3, (
        f"Diharapkan minimal 3 konstruksi BankAccount(...), ditemukan "
        f"{len(konstruksi)}. Kalau ada jalur baca baru, ia juga harus lengkap."
    )

    masalah = []
    for s in konstruksi:
        disebut = {kw.arg for kw in s.keywords if kw.arg}
        kurang = kolom - disebut
        if kurang:
            masalah.append(f"baris {s.lineno}: kurang {sorted(kurang)}")
    assert not masalah, (
        "Konstruksi BankAccount(...) yang tidak menyebut seluruh kolom:\n  "
        + "\n  ".join(masalah)
    )


def test_banks_all_tidak_membaca_cache_redis():
    """
    Cache Redis "bank_account" tidak pernah disegarkan oleh update_bank_account
    dan hanya memuat empat bidang. Selama banks/all membacanya, setiap kolom
    baru — dan setiap perubahan nama rekening — tidak pernah sampai ke layar.
    """
    isi = BERKAS_CTRL.read_text(encoding="utf-8")
    pohon = ast.parse(isi)
    baris = isi.splitlines()

    fungsi = None
    for s in ast.walk(pohon):
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            s.name == "get_all_bank_accounts"
        ):
            fungsi = s
            break
    assert fungsi is not None, "get_all_bank_accounts tidak ditemukan"

    badan = "\n".join(baris[fungsi.lineno - 1 : fungsi.end_lineno])
    assert "lrange" not in badan, (
        "get_all_bank_accounts masih membaca cache Redis. Endpoint banks/all "
        "dipakai 18 layar; sumbernya harus basis data."
    )
    assert "excludeFromCalendar" in badan, (
        "get_all_bank_accounts tidak mengembalikan excludeFromCalendar, "
        "sehingga pemilih rekening kalender akan menganggap semua rekening ikut."
    )
