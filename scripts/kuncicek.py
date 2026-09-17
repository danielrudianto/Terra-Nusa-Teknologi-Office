#!/usr/bin/env python3
"""
Tabel yang punya `rowVersion` harus BENAR-BENAR memakainya.

KENAPA PEMERIKSA INI ADA

Penguncian optimistik dipasang bertahap. `sql/kunci-optimistik.sql` menambahkan
kolom `rowVersion` ke LIMA tabel sekaligus — satu kali perubahan skema, selesai
— sementara penyambungan kodenya menyusul per dokumen.

Keadaan setengah jadi itu berbahaya dengan cara yang khas: kolomnya ada,
skemanya terlihat benar, dan siapa pun yang memeriksa sekilas akan
menyimpulkan dokumen itu sudah terlindungi. Padahal selama tidak ada yang
memanggil `perbarui_terkunci`, dua orang tetap dapat saling menimpa persis
seperti sebelumnya.

Jadi berkas ini menjawab satu pertanyaan yang tidak dapat dijawab dengan
membaca skema: MANA yang sudah tersambung, dan mana yang baru punya kolomnya.

KELUARANNYA BUKAN KEGAGALAN

Tabel yang belum tersambung DILAPORKAN, bukan membuat pemeriksanya merah —
karena penyambungan bertahap memang disengaja, dan pemeriksa yang merah untuk
rencana yang sedang berjalan akan segera dilewati orang.

Yang membuatnya merah hanya kemunduran: tabel yang PERNAH tersambung lalu
tidak lagi.

CARA PAKAI

    ./env/bin/python scripts/kuncicek.py
"""

import pathlib
import re
import sys

AKAR = pathlib.Path(__file__).resolve().parents[1]

# Tabel yang mendapat kolomnya di `sql/kunci-optimistik.sql`, beserta berkas
# yang bertanggung jawab menyambungkannya.
TABEL = {
    "certificate_of_payments": (
        "repository/certificate_of_payment_repository.py",
        "controllers/certificate_of_payment_controller.py",
    ),
    "expenses": ("repository/expense_repository.py",),
    "purchases": ("repository/purchase_repository.py",),
    "purchase_orders": ("repository/purchase_order_repository.py",),
    "tenders": ("repository/tender_repository.py",),
}

# Yang SUDAH tersambung. Menambah nama ke sini adalah cara menyatakan
# "dokumen ini selesai" — dan sejak saat itu pemeriksanya menjaga agar tidak
# mundur lagi.
SUDAH = {"certificate_of_payments", "expenses"}


def _memakai_kunci(berkas: pathlib.Path) -> bool:
    if not berkas.exists():
        return False
    isi = berkas.read_text(encoding="utf-8")
    return "perbarui_terkunci" in isi or "klaim_versi" in isi


def periksa() -> tuple[list[str], list[str]]:
    masalah: list[str] = []
    belum: list[str] = []

    sql = AKAR / "sql" / "kunci-optimistik.sql"
    isi_sql = sql.read_text(encoding="utf-8") if sql.exists() else ""

    for tabel, berkas_terkait in TABEL.items():
        if f"'{tabel}'" not in isi_sql:
            masalah.append(
                f"{tabel}: tidak ada di sql/kunci-optimistik.sql — kodenya "
                f"akan menulis ke kolom yang tidak ada di basis data"
            )

        tersambung = any(_memakai_kunci(AKAR / f) for f in berkas_terkait)

        if tabel in SUDAH and not tersambung:
            masalah.append(
                f"{tabel}: DINYATAKAN sudah terkunci, tetapi tidak satu pun "
                f"dari {', '.join(berkas_terkait)} memanggil "
                f"`perbarui_terkunci`/`klaim_versi` — perlindungannya hilang "
                f"sementara kolomnya tetap ada, jadi tidak ada yang terlihat "
                f"berubah"
            )
        elif tabel not in SUDAH and not tersambung:
            belum.append(tabel)
        elif tabel not in SUDAH and tersambung:
            belum.append(f"{tabel}  (sudah tersambung — tambahkan ke SUDAH)")

    return masalah, belum


if __name__ == "__main__":
    h, belum = periksa()

    print(f"kunci optimistik: {len(h)}")
    print()
    for x in h:
        print(f"  {x}")

    if belum:
        print()
        print("  Belum tersambung (bukan kegagalan — penyambungannya bertahap):")
        for x in belum:
            print(f"    - {x}")
        print()
        print("  Kolomnya sudah ada, tetapi dua orang masih dapat saling")
        print("  menimpa pada dokumen-dokumen itu.")

    sys.exit(1 if h else 0)
