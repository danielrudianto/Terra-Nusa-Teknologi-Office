"""
`current_user` adalah Record, BUKAN dict — jangan panggil `.get()` padanya.

KENAPA PENJAGA INI ADA

Objek yang dikembalikan `require()` berupa `Record` dari pustaka `databases`.
Ia tidak punya `.get()`. Memanggilnya melempar AttributeError DI DALAM RUTE,
yaitu di luar `try/except` milik controller — sehingga yang terjadi bukan
angka yang salah melainkan SELURUH halaman gagal dimuat, dengan pesan
"Tindakan gagal dijalankan" yang tidak menyebut sebabnya.

Sudah terjadi pada `finance_status_routes`: halaman Posisi Keuangan kosong
seluruhnya, sementara jalan keluar `akurasi-rencana` tetap bekerja karena ia
tidak menyentuh objek pengguna. Halaman yang separuhnya hidup itu menyesatkan
ke arah data, alih-alih ke arah rutenya.

Uji biasa tidak menangkapnya: rutenya tidak pernah dipanggil dengan Record
sungguhan, dan controller-nya lolos sendiri karena memang tidak bersalah.

Jebakan ini sudah tertulis di CLAUDE.md dan sudah dijelaskan panjang lebar
pada `_level()` di `agenda_routes.py` — dan tetap terulang. Yang tertulis di
panduan tidak menahan apa pun; yang menahan adalah berkas ini.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTE = os.path.join(AKAR, "routes")

#: `<sesuatu>_user.get(` dan `user.get(` — objek pengguna dari `require()`
#: maupun `get_current_user`.
POLA = re.compile(r"\b(current_user|user)\.get\s*\(")


def test_tidak_ada_rute_yang_memanggil_get_pada_objek_pengguna():
    temuan = []
    for nama in sorted(os.listdir(RUTE)):
        if not nama.endswith(".py"):
            continue
        jalur = os.path.join(RUTE, nama)
        for no, baris in enumerate(
            open(jalur, encoding="utf-8").read().split("\n"), 1
        ):
            bersih = baris.split("#", 1)[0]
            if POLA.search(bersih):
                temuan.append(f"routes/{nama}:{no} -> {baris.strip()}")

    assert not temuan, (
        "objek pengguna adalah Record dan tidak punya .get(); pakai "
        'user["kolom"] atau helper _level()/_id(). '
        "Permintaannya akan gagal 500 tanpa menyebut sebabnya:\n  "
        + "\n  ".join(temuan)
    )


def test_penjaga_ini_benar_benar_memindai_berkas_rute():
    """Penjaga yang tidak menemukan berkas apa pun meluluskan apa saja."""
    berkas = [n for n in os.listdir(RUTE) if n.endswith(".py")]
    assert len(berkas) > 20, f"hanya {len(berkas)} berkas rute terbaca"
