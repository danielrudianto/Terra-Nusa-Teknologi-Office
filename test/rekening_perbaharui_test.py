"""
Menyunting rekening bank tidak boleh gagal gara-gara bidang turunan.

Rute `PUT /banks/{id}` mengirim `BankAccount.model_dump()`. Model Pydantic itu
memuat `balance` — saldo yang dihitung dari mutasi, BUKAN kolom
`bank_accounts`. Meneruskannya apa adanya ke `.values()` membuat SQLAlchemy
melempar `Unconsumed column names: balance`; galatnya ketangkap
`except Exception` di controller dan keluar sebagai 500 yang hanya berbunyi
"Terjadi kesalahan pada sistem".

Karena sebabnya tidak pernah disebut, kegagalannya tampak seperti masalah lain
sama sekali — dan menyunting rekening tidak pernah berhasil sekali pun.

Yang dijaga di sini kelasnya, bukan satu bidang: bidang APA PUN pada model
Pydantic yang bukan kolom tabel tidak boleh sampai ke pernyataan UPDATE.
"""

import os

from sqlalchemy import update

from models.bank_model import bank_accounts_table
from repository.bank_account_repository import BankAccount, kolom_dapat_diubah

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _muatan_rute() -> dict:
    """Persis yang dikirim rute: `BankAccount(...).model_dump()`."""
    return BankAccount(
        id=9,
        bankName="PT Bank Rakyat Indonesia (Persero), Tbk",
        bankAccountName="Deposit",
        bankAccountNumber="00000000",
        excludeFromCalendar=True,
    ).model_dump()


def test_muatan_rute_memang_memuat_bidang_di_luar_kolom():
    """
    Prasyarat bagi uji di bawahnya.

    Bila suatu saat model Pydantic tidak lagi punya bidang turunan, uji
    berikutnya tetap lulus tetapi berhenti menguji apa pun. Ini yang
    memastikan bahayanya masih nyata.
    """
    luar = set(_muatan_rute()) - {c.name for c in bank_accounts_table.columns}
    assert "balance" in luar, (
        "BankAccount.model_dump() tidak lagi memuat `balance` — perbarui uji ini"
    )


def test_pernyataan_update_dapat_dikompilasi():
    """Inilah yang dulu melempar `Unconsumed column names: balance`."""
    nilai = kolom_dapat_diubah(_muatan_rute())
    query = (
        update(bank_accounts_table)
        .where(bank_accounts_table.c.id == 9)
        .values(**nilai)
    )
    str(query.compile())  # tidak boleh melempar


def test_kolom_pembuatan_tidak_ikut_tertimpa():
    """
    createdAt dan createdBy datang dari klien dan kerap kosong.

    `BankAccount.__init__` mengisi createdAt dengan dt.now() bila None, jadi
    tanpa saringan setiap penyuntingan menimpa tanggal pembuatan dan menghapus
    pencatat aslinya — justru jejak yang audit log dibuat untuk menjaganya.
    """
    nilai = kolom_dapat_diubah(_muatan_rute())
    for k in ("id", "createdAt", "createdBy"):
        assert k not in nilai, f"{k} tidak boleh ikut diubah dari muatan klien"


def test_kolom_yang_memang_disunting_tetap_lolos():
    nilai = kolom_dapat_diubah(_muatan_rute())
    assert nilai["bankAccountName"] == "Deposit"
    assert nilai["bankAccountNumber"] == "00000000"
    assert nilai["excludeFromCalendar"] is True


def test_controller_memakai_saringan():
    """Saringannya tidak berguna bila controller tetap meneruskan salinan mentah."""
    s = open(os.path.join(AKAR, "controllers", "bank_controller.py")).read()
    i = s.index("async def update_bank_account(")
    j = s.find("async def ", i + 10)
    blok = s[i:] if j == -1 else s[i:j]
    # Komentar dibuang: keterangan yang MENYEBUT kode lama bukan kode lama.
    blok = "\n".join(
        b for b in blok.splitlines() if not b.lstrip().startswith("#")
    )

    assert "kolom_dapat_diubah(" in blok, (
        "update_bank_account tidak menyaring muatan klien"
    )
    assert "bank_data.copy()" not in blok, (
        "update_bank_account masih meneruskan salinan mentah muatan klien"
    )
