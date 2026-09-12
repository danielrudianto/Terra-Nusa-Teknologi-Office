"""
Konfigurasi bersama untuk pengujian backend.

Dua hal disiapkan di sini:

1. Variabel lingkungan. Modul `utils.database` membacanya saat di-import dan
   akan gagal bila kosong, padahal pengujian tidak menyentuh basis data.
2. Fixture `fake_db`. Repository memanggil objek `database` global; fixture
   ini menggantinya dengan tiruan sehingga pengujian berjalan tanpa MySQL
   dan tanpa mengubah kode produksi.
"""

import os
import sys
from pathlib import Path

import pytest

# Jalankan pengujian dari mana saja: pastikan akar proyek ada di sys.path.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Basis data UJI untuk pengujian integrasi.
#
# Bila `TEST_DATABASE_URL` disetel, seluruh aplikasi diarahkan ke sana —
# termasuk `utils/database.py`, yang membaca `DATABASE_URL` pada saat DI-IMPOR,
# bukan saat dipakai. Karena itu penyetelannya harus berada di baris paling
# atas berkas ini, sebelum satu pun modul aplikasi disentuh.
#
# Tanpa variabel itu, pengujian integrasi TIDAK berjalan sama sekali. Ia
# memanggil endpoint sungguhan dan MENULIS ke basis datanya; menjalankannya
# tanpa ditunjuk secara sengaja berarti menulis ke basis data produksi.
UJI_DB = os.environ.get("TEST_DATABASE_URL")
if UJI_DB:
    os.environ["DATABASE_URL"] = UJI_DB

os.environ.setdefault("DATABASE_URL", "mysql://user:pass@localhost/test_db")
# Kunci uji PANJANGNYA SAMA dengan yang dituntut produksi: 32 bita.
#
# Yang lama `"test-secret-key"` — lima belas aksara — dan PyJWT
# memperingatkannya pada setiap deploy: "The HMAC key is 15 bytes long, which
# is below the minimum recommended length of 32 bytes for SHA256."
#
# Peringatan itu menyangkut KUNCI UJI, bukan `SECRET_KEY` produksi. Tetapi
# selama ia muncul, ia tidak dapat dibedakan dari peringatan yang menyangkut
# kunci sungguhan — dan peringatan yang selalu muncul dan selalu boleh
# diabaikan mengajari pembacanya mengabaikan seluruh keluarannya.
#
# Diperbaiki dengan menyamakan panjangnya, bukan dengan membungkam
# peringatannya: kalau suatu saat kunci produksi yang terbaca di sini —
# `setdefault` memakai yang sudah ada di lingkungan bila ada — peringatannya
# akan muncul kembali, dan memang harus.
os.environ.setdefault(
    "SECRET_KEY", "uji-terrabot-kunci-32-bita-penuh!"
)
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")

# Diimpor lewat jalur berkas agar folder ini tidak perlu dijadikan paket
# (tanpa __init__.py) dan tetap jalan dari direktori mana pun.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _fake_db import FakeDatabase  # noqa: E402


@pytest.fixture
def fake_db(monkeypatch):
    """
    Pasang database tiruan pada modul repository yang diminta.

    Contoh:
        db = fake_db('repository.purchase_order_repository')
        db.queue('fetch_val', 7)

    Setiap modul meng-import `database` ke ruang namanya sendiri, jadi
    penggantinya harus dipasang per modul — bukan sekali di utils.database.
    """

    def _install(*module_paths: str) -> FakeDatabase:
        db = FakeDatabase()
        for path in module_paths:
            module = __import__(path, fromlist=["database"])
            monkeypatch.setattr(module, "database", db, raising=False)
        return db

    return _install


# ---------------------------------------------------------------------------
# Pengujian integrasi (memanggil endpoint sungguhan) dilewati secara bawaan.
#
# `client_test.py` membutuhkan server, basis data, dan autentikasi yang hidup.
# Bila gagal dimuat, pytest menghentikan seluruh pengumpulan berkas sehingga
# pengujian lain ikut tidak berjalan — karena itu dilewati kecuali diminta:
#
#     pytest test/client_test.py        # jalankan khusus, saat server siap
# ---------------------------------------------------------------------------
collect_ignore = ["client_test.py"]


# ---------------------------------------------------------------------------
# Tabel yang strukturnya dibaca dari basis data saat modul dimuat.
#
# `models/balance_model.py` dan `models/mutation_model.py` memakai
# `autoload_with=engine`, yang membuka koneksi MySQL pada saat di-import —
# bukan saat dipakai. Pada mesin tanpa basis data, satu import saja
# menghentikan seluruh pengumpulan pengujian.
#
# Keduanya digantikan tabel kosong dengan nama yang sama. Pengujian yang
# benar-benar membutuhkan strukturnya harus memakai basis data sungguhan dan
# tidak berjalan di sini.
# ---------------------------------------------------------------------------
def _pasang_tabel_tiruan() -> None:
    import types

    from sqlalchemy import Column, Integer, MetaData, Table

    meta = MetaData()

    for nama_modul, nama_tabel, nama_atribut, nama_kelas in (
        ("models.balance_model", "balance", "balance_view", "Balance"),
        ("models.mutation_model", "mutation", "mutation_view", "Mutation"),
    ):
        if nama_modul in sys.modules:
            continue
        modul = types.ModuleType(nama_modul)
        setattr(
            modul,
            nama_atribut,
            Table(nama_tabel, meta, Column("id", Integer, primary_key=True)),
        )
        # Kelas skema ikut disediakan; modul aslinya mengekspor keduanya.
        setattr(modul, nama_kelas, type(nama_kelas, (), {}))
        sys.modules[nama_modul] = modul



# Tabel tiruan hanya dipasang pada pengujian TANPA basis data.
#
# Pada pengujian integrasi keduanya harus yang asli: `balance` menentukan
# apakah rekening boleh dihapus, dan `mutation` dipakai kalender. Tiruan yang
# ikut terpasang membuat uji integrasi menguji tabel kosong buatan sendiri.
if not UJI_DB:
    _pasang_tabel_tiruan()

