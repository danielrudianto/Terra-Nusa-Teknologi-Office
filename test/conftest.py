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

os.environ.setdefault("DATABASE_URL", "mysql://user:pass@localhost/test_db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
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
