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
    # Sebagian repository dinamai dalam bahasa Indonesia, dan daftar yang
    # hanya berbahasa Inggris membuat pemeriksa ini BUTA terhadapnya.
    #
    # Itu bukan kemungkinan yang dikarang: `TenderController.ubah` menulis ke
    # `tenders` lalu ke `tender_items` tanpa transaksi, dan tidak pernah
    # terhitung sebagai satu pun penulisan — sehingga tender yang disunting
    # tersimpan separuh sementara layar menampilkan galat.
    "ubah",
    "buat",
    "hapus",
    "tambah",
    "tulis",
    "simpan",
    "tandai",
    "catat",
    "perbarui",
)

# Fungsi yang sengaja dikecualikan, beserta ALASANNYA.
#
# Daftar ini harus tetap pendek dan setiap barisnya harus dapat dibaca orang
# lain. Pengecualian tanpa alasan adalah cara pemeriksa mati perlahan.
DIKECUALIKAN: dict[tuple[str, str], str] = {}


#: Panggilan yang MEMANG menulis, apa pun namanya.
#:
#: Menebak dari nama method saja terbukti bocor: `perbarui_terkunci` dipanggil
#: sebagai fungsi lepas (bukan atribut) sehingga tidak terhitung, dan
#: `database.execute` — primitif tulis yang sebenarnya di repo ini — tidak
#: mengandung satu pun kata tulis. Keduanya bersama-sama membuat
#: `TenderRepository.ubah` terbaca sebagai satu penulisan padahal dua.
PANGGILAN_TULIS = ("database.execute",)


def _jumlah_penulisan(fn: ast.AST, dalam_kelas: dict | None = None) -> int:
    """
    Berapa kali fungsi ini menulis ke basis data.

    `dalam_kelas` memetakan nama method -> simpulnya, dipakai untuk menembus
    SATU lapis pembantu privat di kelas yang sama. Tanpa itu, memindahkan
    penulisan kedua ke sebuah `_pembantu()` cukup untuk menghilang dari
    pemeriksaan ini — dan persis begitulah bentuk `ubah` yang bermasalah:
    satu penulisan di badannya, satu lagi di `_tulis_baris`.
    """
    n = 0
    for simpul in ast.walk(fn):
        if not isinstance(simpul, ast.Await):
            continue
        panggilan = simpul.value
        if not isinstance(panggilan, ast.Call):
            continue

        teks = ast.unparse(panggilan.func)
        if teks in PANGGILAN_TULIS:
            n += 1
            continue

        if isinstance(panggilan.func, ast.Attribute):
            nama = panggilan.func.attr
        elif isinstance(panggilan.func, ast.Name):
            nama = panggilan.func.id
        else:
            continue

        # Pembantu di kelas yang sama: penulisannya ikut dihitung, satu lapis.
        if dalam_kelas is not None and nama in dalam_kelas:
            n += _jumlah_penulisan(dalam_kelas[nama], None)
            continue

        if any(k in nama.lower() for k in KATA_TULIS):
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

    # ------------------------------------------------------------------
    # PENULISAN GANDA YANG BERSEMBUNYI DI REPOSITORY
    #
    # Menghitung panggilan di controller saja TIDAK CUKUP, dan itu terbukti
    # mahal. `TenderController.ubah` hanya memanggil `TenderRepository.ubah`
    # satu kali — terlihat tunggal, lolos pemeriksaan ini — padahal fungsi
    # repository itulah yang menulis ke `tenders` lalu ke `tender_items`.
    # Ketika penulisan kedua gagal, kepala tendernya sudah tersimpan dan
    # layar menampilkan galat: data berubah sementara penggunanya yakin
    # simpanannya batal.
    #
    # Jadi repository ikut dibaca: fungsi yang menulis lebih dari sekali
    # dicatat namanya, lalu setiap fungsi controller yang memanggilnya wajib
    # atomik. Yang dijaga tetap hal yang sama — satu tindakan, satu
    # transaksi — hanya saja kini terlihat menembus satu lapis.
    # ------------------------------------------------------------------
    # Dicatat LENGKAP dengan nama kelasnya — `TenderRepository.ubah`, bukan
    # `ubah`. Mencocokkan nama telanjang membuat setiap repository yang punya
    # method bernama `update` ikut terseret: satu `update` yang menulis ganda
    # akan menuduh seluruh controller yang memanggil `update` milik siapa pun.
    penulis_ganda: set[str] = set()
    for berkas in sorted((AKAR / "repository").glob("*.py")):
        sumber = berkas.read_text(encoding="utf-8")
        try:
            pohon = ast.parse(sumber)
        except SyntaxError:
            continue
        for kelas in ast.walk(pohon):
            if not isinstance(kelas, ast.ClassDef):
                continue
            sekelas = {
                f.name: f
                for f in kelas.body
                if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            for fn in kelas.body:
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                potongan = ast.get_source_segment(sumber, fn) or ""
                if "transaction()" in potongan:
                    continue
                if _jumlah_penulisan(fn, sekelas) >= 2:
                    penulis_ganda.add(f"{kelas.name}.{fn.name}")

    for berkas in sorted((AKAR / "controllers").glob("*.py")):
        sumber = berkas.read_text(encoding="utf-8")
        try:
            pohon = ast.parse(sumber)
        except SyntaxError:
            continue
        for fn in ast.walk(pohon):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if (berkas.name, fn.name) in DIKECUALIKAN:
                continue
            if "atomik" in [ast.unparse(d) for d in fn.decorator_list]:
                continue
            potongan = ast.get_source_segment(sumber, fn) or ""
            if "transaction()" in potongan:
                continue
            dipanggil = sorted(
                {
                    ast.unparse(simpul.value.func)
                    for simpul in ast.walk(fn)
                    if isinstance(simpul, ast.Await)
                    and isinstance(simpul.value, ast.Call)
                    and isinstance(simpul.value.func, ast.Attribute)
                    and ast.unparse(simpul.value.func) in penulis_ganda
                }
            )
            if dipanggil:
                masalah.append(
                    f"{berkas.name}::{fn.name} memanggil "
                    f"{', '.join(dipanggil)} — yang menulis ke lebih dari "
                    f"satu tabel — tanpa transaksi. Bila penulisan kedua "
                    f"gagal, yang pertama TETAP tersimpan sementara layar "
                    f"menampilkan galat. Tambahkan `@atomik` di bawah "
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
