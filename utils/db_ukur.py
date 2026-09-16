"""
Penghitung kueri per permintaan HTTP.

KENAPA INI ADA

Sudah ada pencatat permintaan lambat di `main.py`: ia memberi tahu permintaan
MANA yang lambat. Yang belum terjawab adalah KENAPA — dan tanpa itu, langkah
berikutnya selalu tebakan.

Dua sebab yang paling sering, dan yang penanganannya berlawanan:

  * SATU kueri yang lambat. Biasanya indeks yang kurang, atau `LIKE '%x%'`
    yang tidak dapat memakai indeks apa pun. Yang perlu diperbaiki kuerinya.
  * RATUSAN kueri yang masing-masing cepat — N+1. Perulangan yang menembak
    basis data sekali untuk setiap baris. Yang perlu diperbaiki bentuk
    pengambilannya, bukan kuerinya.

Dari waktu total saja keduanya tidak dapat dibedakan; 2 detik terlihat sama
persis. Dari jumlah kuerinya, bedanya langsung terbaca:

    X-Response-Time-ms: 2300   X-Db-Queries: 3     -> satu kueri lambat
    X-Response-Time-ms: 2300   X-Db-Queries: 412   -> N+1

CATATAN JUJUR SOAL BIAYANYA

Penghitungnya sendiri hampir tidak berbiaya — satu `perf_counter()` dan satu
penambahan per kueri — tetapi ia TIDAK gratis dan ia membungkus jalur yang
paling panas di sistem ini. Karena itu ia dapat dimatikan sepenuhnya lewat
`DB_UKUR=0`, dan saat mati, method-methodnya tidak dibungkus sama sekali.

AMAN UNTUK ASYNC

Dipakai `ContextVar`, sama seperti `audit_context`: tiap permintaan punya
salinan konteksnya sendiri, jadi dua pengguna yang bersamaan tidak saling
menambahi hitungan. Yang disimpan adalah satu dict yang DIUBAH ISINYA, bukan
diganti — middleware menaruhnya sebelum permintaan diproses dan membacanya
sesudahnya, dan perubahan di dalamnya terlihat karena objeknya sama.
"""

import os
import time
from contextvars import ContextVar
from typing import Any

from databases import Database

_ukuran: ContextVar[dict | None] = ContextVar("db_ukuran", default=None)

# Dapat dimatikan tanpa mengubah kode. Nilai apa pun selain "0" berarti nyala.
AKTIF = os.getenv("DB_UKUR", "1") != "0"


def mulai_ukur() -> dict:
    """Pasang penghitung baru untuk permintaan ini, dan kembalikan wadahnya."""
    wadah = {"n": 0, "ms": 0.0}
    _ukuran.set(wadah)
    return wadah


def _catat(lama_ms: float) -> None:
    wadah = _ukuran.get()
    if wadah is None:
        # Di luar permintaan HTTP — tugas latar, skrip, uji. Tidak dihitung,
        # dan tidak dianggap galat: ini jalur yang sah.
        return
    wadah["n"] += 1
    wadah["ms"] += lama_ms


class DatabaseTerukur(Database):
    """
    `databases.Database` yang menghitung kuerinya.

    Dibungkus dengan pewarisan, bukan dengan menambal modulnya. Menambal
    berarti siapa pun yang membaca `utils/database.py` melihat `Database`
    biasa dan tidak punya cara mengetahui bahwa perilakunya sudah berbeda —
    dan itu persis jenis kejutan yang mahal ditelusuri jam dua pagi.
    """

    async def fetch_all(self, *a: Any, **k: Any):
        mulai = time.perf_counter()
        try:
            return await super().fetch_all(*a, **k)
        finally:
            # `finally`, bukan sesudah `return`: kueri yang GAGAL adalah yang
            # paling perlu terlihat — misalnya yang kehabisan waktu tunggu.
            _catat((time.perf_counter() - mulai) * 1000)

    async def fetch_one(self, *a: Any, **k: Any):
        mulai = time.perf_counter()
        try:
            return await super().fetch_one(*a, **k)
        finally:
            _catat((time.perf_counter() - mulai) * 1000)

    async def fetch_val(self, *a: Any, **k: Any):
        mulai = time.perf_counter()
        try:
            return await super().fetch_val(*a, **k)
        finally:
            _catat((time.perf_counter() - mulai) * 1000)

    async def execute(self, *a: Any, **k: Any):
        mulai = time.perf_counter()
        try:
            return await super().execute(*a, **k)
        finally:
            _catat((time.perf_counter() - mulai) * 1000)

    async def execute_many(self, *a: Any, **k: Any):
        mulai = time.perf_counter()
        try:
            return await super().execute_many(*a, **k)
        finally:
            _catat((time.perf_counter() - mulai) * 1000)
