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

# Yang SUDAH tersambung, BACKEND DAN LAYARNYA. Menambah nama ke sini adalah
# cara menyatakan "dokumen ini selesai" — dan sejak saat itu pemeriksanya
# menjaga agar tidak mundur lagi.
SUDAH = {"certificate_of_payments", "expenses", "purchase_orders", "purchases"}

# Keadaan KETIGA, dan sebab ia ada.
#
# Backendnya memanggil `perbarui_terkunci`, tetapi layarnya belum mengirim
# `rowVersion` sama sekali. Helper-nya memperlakukan versi yang tidak
# disebutkan sebagai "simpan tanpa penjagaan" — disengaja, supaya jeda antara
# kedua deploy tidak menghentikan seluruh penyuntingan — sehingga pada keadaan
# ini perlindungannya BELUM menyala walaupun kodenya sudah terpasang.
#
# Tanpa keadaan ini pemeriksanya hanya punya dua kotak, dan begitu backendnya
# tersambung ia mencetak "tambahkan ke SUDAH" — mendorong yang membacanya
# menyatakan selesai untuk sesuatu yang belum melindungi apa pun. Pemeriksa
# yang memaksa orang berbohong lebih buruk daripada tidak ada pemeriksa.
#
# Nilainya menyebut APA yang masih kurang, supaya yang meneruskan tahu persis
# di mana pekerjaannya berhenti.
#
# `purchase_orders` pernah di sini ("16 ragam formulir belum mengirim
# `rowVersion`"). Keenam belasnya kini mengirim versinya lewat
# `AdendumService.denganVersi()`, dan yang menjaga agar formulir ketujuh
# belas tidak lupa adalah `scripts/pemeriksa/versipocek.py` di repo frontend
# — pemeriksa di sini tidak dapat melihat berkas layar.
SEPARUH: dict[str, str] = {}


def _memakai_kunci(berkas: pathlib.Path) -> bool:
    if not berkas.exists():
        return False
    isi = berkas.read_text(encoding="utf-8")
    return "perbarui_terkunci" in isi or "klaim_versi" in isi


def periksa() -> tuple[list[str], list[str], list[str]]:
    masalah: list[str] = []
    belum: list[str] = []
    separuh: list[str] = []

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
        elif tabel in SEPARUH and not tersambung:
            # Kemunduran juga, dengan bentuk yang berbeda: backendnya pernah
            # tersambung lalu panggilannya hilang.
            masalah.append(
                f"{tabel}: DINYATAKAN separuh tersambung, tetapi tidak satu "
                f"pun dari {', '.join(berkas_terkait)} memanggil "
                f"`perbarui_terkunci`/`klaim_versi` lagi"
            )
        elif tabel in SUDAH:
            # Tersambung dan dinyatakan selesai: tidak ada yang perlu
            # dilaporkan.
            continue
        elif tabel in SEPARUH:
            separuh.append(f"{tabel}: {SEPARUH[tabel]}")
        elif not tersambung:
            belum.append(tabel)
        else:
            belum.append(f"{tabel}  (sudah tersambung — tambahkan ke SUDAH)")

    return masalah, belum, separuh


if __name__ == "__main__":
    h, belum, separuh = periksa()

    print(f"kunci optimistik: {len(h)}")
    print()
    for x in h:
        print(f"  {x}")

    if separuh:
        print()
        print("  Backendnya tersambung, LAYARNYA BELUM — jadi penjagaannya")
        print("  belum menyala sama sekali:")
        for x in separuh:
            print(f"    - {x}")

    if belum:
        print()
        print("  Belum tersambung (bukan kegagalan — penyambungannya bertahap):")
        for x in belum:
            print(f"    - {x}")
        print()
        print("  Kolomnya sudah ada, tetapi dua orang masih dapat saling")
        print("  menimpa pada dokumen-dokumen itu.")

    sys.exit(1 if h else 0)
