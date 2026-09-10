#!/usr/bin/env python3
"""
Menambal backend untuk fitur "kecualikan rekening dari kalender".

Dijalankan dari akar repositori backend:

    python3 scripts/tambal-rekening-kalender.py          # tambal
    python3 scripts/tambal-rekening-kalender.py --periksa # hanya periksa

Skrip ini SENGAJA berhenti dengan berisik bila ada satu saja jangkar yang
tidak ditemukan. Berkas backend tidak pernah ditulis ulang dari salinan lama;
yang ditambal hanya baris yang jangkarnya cocok persis. Bila jangkarnya
berubah, skripnya gagal — bukan berkasnya yang rusak diam-diam.

Aman dijalankan berulang kali (idempoten).
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys

KOLOM = "excludeFromCalendar"

GAGAL: list[str] = []
BERUBAH: list[str] = []
LEWAT: list[str] = []


def gagal(pesan: str) -> None:
    GAGAL.append(pesan)


# Berkas repo ini berakhiran CRLF. Ditangani secara sadar: dibaca mentah,
# dinormalkan ke \n selama ditambal, lalu dikembalikan ke akhiran aslinya.
# Tanpa ini seluruh berkas akan tampak berubah pada git diff, dan perubahan
# yang sebenarnya jadi tidak bisa diperiksa siapa pun.
_AKHIRAN: dict[str, str] = {}


def baca(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", newline="") as f:
        mentah = f.read()
    _AKHIRAN[os.path.abspath(path)] = "\r\n" if "\r\n" in mentah else "\n"
    return mentah.replace("\r\n", "\n")


def tulis(path: str, isi: str, kering: bool) -> None:
    if kering:
        return
    akhiran = _AKHIRAN.get(os.path.abspath(path), "\n")
    if akhiran != "\n":
        isi = isi.replace("\n", akhiran)
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(isi)


# --------------------------------------------------------------------------
# 1. models/bank_model.py — kolom tabel
# --------------------------------------------------------------------------
def tambal_model(kering: bool) -> None:
    path = "models/bank_model.py"
    if not os.path.exists(path):
        gagal(f"{path} tidak ditemukan. Jalankan skrip ini dari akar repo backend.")
        return

    src = baca(path)
    if KOLOM in src:
        LEWAT.append(f"{path}: kolom {KOLOM} sudah ada")
        return

    # Jangkarnya baris Column untuk isDelete, apa pun gaya penulisannya.
    pola = re.compile(
        r'^([ \t]*)Column\(\s*[\'"]isDelete[\'"].*?\)\s*,?\s*$',
        re.MULTILINE,
    )
    cocok = list(pola.finditer(src))
    if len(cocok) != 1:
        gagal(
            f"{path}: mencari satu baris Column(\"isDelete\", ...) tetapi menemukan "
            f"{len(cocok)}. Tambahkan sendiri baris berikut ke bank_accounts_table:\n"
            f'    Column("{KOLOM}", Boolean, nullable=False, server_default="0"),'
        )
        return

    m = cocok[0]
    indent = m.group(1)
    baris_baru = (
        f'{indent}# Rekening yang dikecualikan tidak ikut dijumlahkan pada saldo\n'
        f'{indent}# gabungan maupun proyeksi kalender (mis. deposit jaminan).\n'
        f'{indent}Column("{KOLOM}", Boolean, nullable=False, server_default="0"),'
    )
    src = src[: m.end()] + "\n" + baris_baru + src[m.end() :]

    if "Boolean" not in src.split("bank_accounts_table")[0]:
        gagal(
            f"{path}: 'Boolean' sepertinya belum di-import. Tambahkan pada baris "
            f"import sqlalchemy."
        )

    tulis(path, src, kering)
    BERUBAH.append(f"{path}: kolom {KOLOM} ditambahkan setelah isDelete")


# --------------------------------------------------------------------------
# 2. repository/bank_account_repository.py — model Pydantic + 4 query
# --------------------------------------------------------------------------
def tambal_repository(kering: bool) -> None:
    path = "repository/bank_account_repository.py"
    if not os.path.exists(path):
        gagal(f"{path} tidak ditemukan.")
        return

    src = baca(path)
    asal = src

    # 2a. Bidang pada model Pydantic.
    #     Pydantic MEMBUANG DIAM-DIAM bidang yang tidak dideklarasikan, jadi
    #     tanpa baris ini seluruh sisanya tidak ada gunanya.
    if re.search(rf"^\s*{KOLOM}\s*:", src, re.MULTILINE) is None:
        jangkar = "    isDelete: bool = False  # Flag to indicate if the purchase is deleted\n"
        if jangkar not in src:
            gagal(f"{path}: jangkar bidang isDelete pada model Pydantic tidak ditemukan.")
        else:
            src = src.replace(
                jangkar,
                jangkar
                + f"    {KOLOM}: bool = False  # Dikecualikan dari saldo gabungan dan kalender\n",
                1,
            )

    # 2b. create() — .values(...)
    if f"{KOLOM}=self.{KOLOM}" not in src:
        jangkar = "                isDelete=self.isDelete,\n"
        if jangkar not in src:
            gagal(f"{path}: jangkar isDelete=self.isDelete pada create() tidak ditemukan.")
        else:
            src = src.replace(
                jangkar, jangkar + f"                {KOLOM}=self.{KOLOM},\n", 1
            )

    # 2c. Tiga konstruksi BankAccount(...) di get_banks,
    #     get_bank_account_by_id, dan get_bank_accounts_by_ids.
    #     Ketiganya menyebut kolom satu per satu, jadi ketiganya membuang
    #     kolom yang tidak disebut.
    pola_row = re.compile(r"^([ \t]*)isDelete=row\.isDelete(,?)[ \t]*$", re.MULTILINE)
    jumlah_row = len(pola_row.findall(src))
    if f"{KOLOM}=bool(getattr(row" not in src:
        if jumlah_row != 3:
            gagal(
                f"{path}: mencari 3 baris 'isDelete=row.isDelete' tetapi menemukan "
                f"{jumlah_row}. Periksa berkasnya sebelum menambal."
            )
        else:
            src = pola_row.sub(
                lambda m: (
                    f"{m.group(1)}isDelete=row.isDelete,\n"
                    f'{m.group(1)}{KOLOM}=bool(getattr(row, "{KOLOM}", False)),'
                ),
                src,
            )

    if src != asal:
        tulis(path, src, kering)
        BERUBAH.append(f"{path}: model Pydantic, create(), dan 3 konstruksi BankAccount")
    else:
        LEWAT.append(f"{path}: sudah tertambal")


# --------------------------------------------------------------------------
# 3. controllers/bank_controller.py — banks/all berhenti membaca Redis
# --------------------------------------------------------------------------
BADAN_BARU = '''    @staticmethod
    async def get_all_bank_accounts() -> List[Dict]:
        """
        Seluruh rekening bank untuk dropdown dan pemilih rekening kalender.

        Sumbernya basis data, BUKAN Redis.

        Cache "bank_account" tidak pernah diperbarui oleh update_bank_account,
        sehingga isinya hanya benar sampai rekening itu pertama kali dibuat.
        Setiap kolom baru — dan setiap perubahan nama rekening — tidak pernah
        sampai ke pemanggil. Kegagalannya sunyi: bidangnya hilang, bukan
        error, jadi tampilannya tampak bekerja padahal nilainya tidak pernah
        terbaca.
        """
        log_info("Getting all bank accounts")
        try:
            query = select(bank_accounts_table).order_by(
                bank_accounts_table.c.isDelete,
                bank_accounts_table.c.bankAccountNumber,
            )
            rows = await database.fetch_all(query)
            return [
                {
                    "id": row.id,
                    "bankName": row.bankName,
                    "bankAccountName": row.bankAccountName,
                    "bankAccountNumber": row.bankAccountNumber,
                    "isDelete": bool(row.isDelete),
                    "excludeFromCalendar": bool(
                        getattr(row, "excludeFromCalendar", False)
                    ),
                }
                for row in rows
            ]
        except Exception as e:
            log_error(f"Error retrieving all bank accounts: {str(e)}")
            return internal_error()
'''


def tambal_controller(kering: bool) -> None:
    path = "controllers/bank_controller.py"
    if not os.path.exists(path):
        gagal(f"{path} tidak ditemukan.")
        return

    src = baca(path)

    # Ganti seluruh badan get_all_bank_accounts, dari dekoratornya sampai
    # tepat sebelum dekorator/def berikutnya.
    pola = re.compile(
        r"    @staticmethod\n"
        r"    async def get_all_bank_accounts\(.*?\n"
        r"(?=    @staticmethod\n|    async def |\Z)",
        re.DOTALL,
    )
    cocok = list(pola.finditer(src))
    if len(cocok) != 1:
        gagal(
            f"{path}: mencari satu definisi get_all_bank_accounts tetapi menemukan "
            f"{len(cocok)}."
        )
        return

    badan_lama = cocok[0].group(0)
    if KOLOM in badan_lama and "database.fetch_all" in badan_lama:
        LEWAT.append(f"{path}: sudah tertambal")
        return
    if 'r.lrange("bank_account"' not in badan_lama:
        gagal(
            f"{path}: get_all_bank_accounts sudah tidak membaca Redis tetapi juga "
            f"belum menyebut {KOLOM}. Bentuknya tidak dikenali — periksa sendiri "
            f"sebelum menambal."
        )
        return

    src = src[: cocok[0].start()] + BADAN_BARU + src[cocok[0].end() :]

    # Sisa kode Redis sekarang tidak dibaca siapa pun. Ditandai, bukan dihapus:
    # kode mati yang tampak hidup itulah yang membuat kolom baru hilang
    # diam-diam sejak awal.
    tanda = (
        "            # CATATAN: cache ini tidak lagi menjadi sumber banks/all.\n"
        "            # Tidak ada yang membacanya; update_bank_account pun tidak\n"
        "            # pernah menyegarkannya. Jangan dijadikan sumber data lagi.\n"
    )
    for jangkar in (
        '            r.rpush("bank_account", json.dumps({\n',
        '            bank_accounts = r.lrange("bank_account", 0, -1)\n',
    ):
        if jangkar in src and "cache ini tidak lagi menjadi sumber" not in src.split(jangkar)[0][-400:]:
            src = src.replace(jangkar, tanda + jangkar, 1)

    tulis(path, src, kering)
    BERUBAH.append(f"{path}: get_all_bank_accounts membaca basis data, bukan Redis")


# --------------------------------------------------------------------------
# 4. Pemeriksaan — hal-hal yang harus diketahui, bukan ditambal diam-diam
# --------------------------------------------------------------------------
def _fungsi_pembungkus(baris_list: list[str], idx: int) -> list[str]:
    """Badan fungsi yang membungkus baris ke-idx (0-based), kasar tapi cukup."""
    mulai = idx
    while mulai > 0 and not re.match(r"\s*(async )?def ", baris_list[mulai]):
        mulai -= 1
    akhir = idx + 1
    while akhir < len(baris_list) and not re.match(
        r"\s*(@staticmethod|(async )?def )", baris_list[akhir]
    ):
        akhir += 1
    return baris_list[mulai:akhir]


def periksa_pembaca_redis_lain() -> None:
    """
    Bila ada tempat lain yang MEMBACA cache bank_account sebagai sumber data,
    kita harus tahu — cache itu tidak pernah disegarkan oleh update.

    lrange yang dipakai untuk memelihara cache-nya sendiri (diikuti lset/rpush
    di fungsi yang sama) bukan pembaca; itu dilewati.
    """
    temuan = []
    for akar, _, berkas in os.walk("."):
        if any(x in akar for x in (".git", "venv", "__pycache__", "node_modules")):
            continue
        for nama in berkas:
            if not nama.endswith(".py"):
                continue
            p = os.path.join(akar, nama)
            if p.endswith("tambal-rekening-kalender.py"):
                continue
            try:
                isi = baca(p)
            except Exception:
                continue
            baris_list = isi.splitlines()
            for i, baris in enumerate(baris_list):
                if 'lrange("bank_account"' not in baris and "lrange('bank_account'" not in baris:
                    continue
                badan = "\n".join(_fungsi_pembungkus(baris_list, i))
                if "r.lset(" in badan or "r.rpush(" in badan:
                    continue  # pemeliharaan cache, bukan sumber baca
                temuan.append(f"{p}:{i + 1}")
    if temuan:
        gagal(
            "Masih ada tempat lain yang membaca cache Redis bank_account sebagai "
            "sumber data, dan cache itu tidak pernah disegarkan oleh "
            "update_bank_account:\n    "
            + "\n    ".join(temuan)
            + "\n  Putuskan dulu: pindahkan juga ke basis data, atau segarkan "
            "cache-nya pada update_bank_account."
        )


def periksa_skema_route() -> None:
    """
    Pydantic membuang bidang yang tidak dideklarasikan tanpa bersuara.

    Bila route bank memakai skema Pydantic sendiri, bidang barunya harus
    dideklarasikan di sana juga — kalau tidak, togel-nya akan tampak
    tersimpan padahal nilainya tidak pernah sampai ke controller.
    """
    kandidat = []
    for akar, _, berkas in os.walk("."):
        if any(x in akar for x in (".git", "venv", "__pycache__", "node_modules")):
            continue
        for nama in berkas:
            if not nama.endswith(".py"):
                continue
            if "bank" not in nama.lower():
                continue
            p = os.path.join(akar, nama)
            if "route" not in p.lower() and "schema" not in p.lower():
                continue
            kandidat.append(p)

    for p in kandidat:
        isi = baca(p)
        if "BaseModel" not in isi:
            continue
        if KOLOM not in isi:
            gagal(
                f"{p}: memakai skema Pydantic tetapi tidak menyebut {KOLOM}. "
                f"Pydantic membuang bidang yang tidak dideklarasikan TANPA error — "
                f"tambahkan '{KOLOM}: bool = False' pada skema create dan update, "
                f"atau pastikan route-nya menerima Dict mentah."
            )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--periksa", action="store_true", help="jangan tulis apa pun")
    arg = ap.parse_args()

    if not os.path.isdir("controllers") or not os.path.isdir("repository"):
        print(
            "Skrip ini harus dijalankan dari akar repositori backend "
            "(yang berisi folder controllers/ dan repository/).",
            file=sys.stderr,
        )
        return 2

    tambal_model(arg.periksa)
    tambal_repository(arg.periksa)
    tambal_controller(arg.periksa)
    periksa_pembaca_redis_lain()
    periksa_skema_route()

    if BERUBAH:
        print("Ditambal:")
        for x in BERUBAH:
            print(f"  - {x}")
    if LEWAT:
        print("Dilewati (sudah sesuai):")
        for x in LEWAT:
            print(f"  - {x}")

    if GAGAL:
        print("\nGAGAL — tidak ada yang boleh dianggap selesai:", file=sys.stderr)
        for x in GAGAL:
            print(f"  * {x}", file=sys.stderr)
        return 1

    print("\nSelesai. Jalankan: pytest tests/rekening_dikecualikan_test.py -q")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
