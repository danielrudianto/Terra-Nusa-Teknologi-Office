#!/usr/bin/env python3
"""
Fungsi controller yang menulis lebih dari sekali WAJIB atomik.

KENAPA PEMERIKSA, BUKAN UJI

Empat belas fungsi sudah dibungkus `@atomik`. Yang tidak dijaga oleh
pembungkusan itu adalah fungsi KELIMA BELAS — yang ditulis bulan depan, oleh
siapa pun, untuk fitur yang belum ada.

Uji hanya dapat memeriksa yang sudah ditulis ujinya. Celah ini bentuknya
"ada kode baru yang lupa sesuatu", dan satu-satunya yang dapat menangkapnya
adalah sesuatu yang membaca SELURUH berkas setiap kali.

Dan celah ini tidak menghasilkan galat apa pun. Fungsi yang menulis dua kali
tanpa transaksi berjalan mulus ribuan kali; ia hanya salah pada kali yang
gagal di tengah — dan yang tertinggal saat itu adalah pembayaran yang
tercatat disetujui di atas pembelian yang tidak lunas.

CARA PAKAI

    ./env/bin/python scripts/atomikcek.py

Keluar dengan kode 1 bila ada temuan, sehingga dapat dipasang di deploy.sh
atau CI.
"""

import ast
import pathlib
import sys

AKAR = pathlib.Path(__file__).resolve().parents[1]

# Nama method repository yang berarti MENULIS. Bukan daftar yang sempurna —
# tetapi salah-tangkap di sini berbiaya satu baris `@atomik` yang tidak perlu,
# sedangkan yang terlewat berbiaya data yang tidak konsisten.
KATA_TULIS = (
    "create",
    "insert",
    "add",
    "update",
    "delete",
    "save",
    "set_",
    "remove",
)

# Fungsi yang sengaja dikecualikan, beserta ALASANNYA.
#
# Daftar ini harus tetap pendek dan setiap barisnya harus dapat dibaca orang
# lain. Pengecualian tanpa alasan adalah cara pemeriksa mati perlahan.
DIKECUALIKAN: dict[tuple[str, str], str] = {}


def _jumlah_penulisan(fn: ast.AST) -> int:
    n = 0
    for simpul in ast.walk(fn):
        if not isinstance(simpul, ast.Await):
            continue
        panggilan = simpul.value
        if not isinstance(panggilan, ast.Call):
            continue
        if not isinstance(panggilan.func, ast.Attribute):
            continue
        nama = panggilan.func.attr.lower()
        if any(k in nama for k in KATA_TULIS):
            n += 1
    return n


def periksa() -> list[str]:
    masalah: list[str] = []

    for berkas in sorted((AKAR / "controllers").glob("*.py")):
        sumber = berkas.read_text(encoding="utf-8")
        try:
            pohon = ast.parse(sumber)
        except SyntaxError as e:
            masalah.append(f"{berkas.name}: tidak dapat diurai — {e}")
            continue

        for fn in ast.walk(pohon):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            kunci = (berkas.name, fn.name)
            if kunci in DIKECUALIKAN:
                continue

            dekorator = [ast.unparse(d) for d in fn.decorator_list]
            if "atomik" in dekorator:
                continue

            # Transaksi yang ditulis tangan di dalam badannya juga sah.
            potongan = ast.get_source_segment(sumber, fn) or ""
            if "transaction()" in potongan:
                continue

            n = _jumlah_penulisan(fn)
            if n >= 2:
                masalah.append(
                    f"{berkas.name}::{fn.name} menulis {n} kali tanpa "
                    f"transaksi — bila salah satunya gagal, yang sudah "
                    f"tertulis TETAP tersimpan. Tambahkan `@atomik` di bawah "
                    f"`@staticmethod`."
                )

    # Urutan dekoratornya penting, dan salahnya baru terasa saat dipanggil.
    for berkas in sorted((AKAR / "controllers").glob("*.py")):
        baris = berkas.read_text(encoding="utf-8").split("\n")
        for i, b in enumerate(baris):
            if b.strip() != "@atomik":
                continue
            if i + 1 < len(baris) and baris[i + 1].strip() == "@staticmethod":
                masalah.append(
                    f"{berkas.name}: `@atomik` ditulis DI ATAS "
                    f"`@staticmethod` (baris {i + 1}) — yang terbungkus "
                    f"objek `staticmethod`, bukan fungsinya, dan hasilnya "
                    f"`TypeError` saat dipanggil, bukan saat dimuat"
                )

    return masalah


if __name__ == "__main__":
    h = periksa()
    print(f"atomik: {len(h)}")
    print()
    for x in h:
        print(f"  {x}")
    sys.exit(1 if h else 0)
