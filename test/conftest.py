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

        # `utils.database` IKUT diganti, selalu.
        #
        # Sebagian penolong bersama — `utils/kunci_optimistik.py` yang
        # paling jelas — sengaja membaca `utils.database.database` pada saat
        # DIPANGGIL, bukan meng-import-nya ke ruang namanya sendiri. Tanpa
        # baris ini, repository yang memakai penolong itu tetap menyentuh
        # objek database yang sungguhan di tengah pengujian tanpa basis
        # data: sambungannya tidak ada, galatnya tertelan `except` di dalam
        # repository, dan yang terlihat hanya "Internal server error" —
        # jalur tulisnya tidak pernah benar-benar diuji.
        import utils.database

        monkeypatch.setattr(utils.database, "database", db, raising=False)
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


# ---------------------------------------------------------------------------
# PRASYARAT DISARING SAAT PENGUMPULAN, BUKAN SAAT UJI DIJALANKAN
#
# Sebelumnya uji yang prasyaratnya tidak ada — basis data uji, `pdftotext`,
# repo frontend di sebelah — dijalankan lalu melapor SKIPPED satu per satu.
# Delapan puluh satu baris "SKIPPED [1] ... TEST_DATABASE_URL belum disetel"
# dengan kalimat yang sama persis, setiap kali, di bawah hasil yang sebenarnya.
#
# Kenapa itu buruk, bukan sekadar berisik: ringkasan yang selalu memuat puluhan
# skip membuat skip BERHENTI BERARTI. Satu uji yang mulai dilewati karena
# sebab yang sungguhan — berkas hilang, prasyarat berubah — tenggelam di antara
# delapan puluh yang memang selalu dilewati, dan tidak ada yang menyadarinya.
#
# Sekarang uji itu tidak ikut dikumpulkan sama sekali: pytest melaporkannya
# sebagai `deselected`, satu angka, dan sebabnya disebut SEKALI di kepala
# keluaran. Yang berjalan berjalan; yang tidak, tidak muncul sebagai hasil.
#
# Penandanya TIDAK diubah. `pytest.mark.skipif` di berkas ujinya tetap menjadi
# satu-satunya sumber kebenaran — hook di bawah hanya membacanya lebih awal.
# Dengan begitu menjalankan satu berkas secara langsung tetap berperilaku
# seperti biasa, dan tidak ada daftar kedua yang harus dijaga tetap sepakat.
# ---------------------------------------------------------------------------

_KUNCI_PRASYARAT = pytest.StashKey[dict]()

#: Sebab yang terbaca orang, diringkas dari `reason` yang panjang.
_RINGKASAN_SEBAB = (
    ("TEST_DATABASE_URL", "butuh basis data uji (TEST_DATABASE_URL)"),
    ("pdftotext", "butuh pdftotext"),
    ("repo frontend", "butuh repo frontend di sebelahnya"),
    ("terjemahan frontend", "butuh berkas terjemahan frontend"),
)


def _sebab_ringkas(alasan: str) -> str:
    for kunci, ringkas in _RINGKASAN_SEBAB:
        if kunci.lower() in (alasan or "").lower():
            return ringkas
    teks = " ".join((alasan or "prasyarat tidak terpenuhi").split())
    return teks[:60]


def _prasyarat_kurang(item):
    """
    Alasan `skipif` yang SUDAH pasti benar sekarang, atau None.

    Hanya kondisi yang sudah berupa boolean yang dibaca — itulah bentuk
    seluruh penanda di repo ini (`not TEST_DB`, `shutil.which(...) is None`),
    dinilai saat modulnya di-import. Kondisi berupa TEKS tidak disentuh:
    menilainya menuntut ruang nama uji yang belum tentu tersedia di sini, dan
    menebaknya akan membuang uji yang sebenarnya harus berjalan.
    """
    for tanda in item.iter_markers(name="skipif"):
        for syarat in tanda.args:
            if isinstance(syarat, bool) and syarat:
                return str(tanda.kwargs.get("reason") or "prasyarat tidak terpenuhi")
    return None


def pytest_collection_modifyitems(config, items):
    jalan, dibuang = [], []
    hitung = {}
    for item in items:
        alasan = _prasyarat_kurang(item)
        if alasan is None:
            jalan.append(item)
            continue
        dibuang.append(item)
        ringkas = _sebab_ringkas(alasan)
        hitung[ringkas] = hitung.get(ringkas, 0) + 1

    if not dibuang:
        return

    # `items[:]` diganti di tempat: pytest memegang daftar yang SAMA.
    items[:] = jalan
    config.hook.pytest_deselected(items=dibuang)
    config.stash[_KUNCI_PRASYARAT] = hitung



def pytest_report_collectionfinish(config, items):
    """Sebabnya disebut SEKALI, di kepala keluaran — bukan per uji di bawah."""
    hitung = config.stash.get(_KUNCI_PRASYARAT, None)
    if not hitung:
        return []
    baris = [
        f"tidak dikumpulkan: {sum(hitung.values())} uji "
        f"({len(items)} dijalankan)"
    ]
    for sebab, n in sorted(hitung.items(), key=lambda kv: -kv[1]):
        baris.append(f"  {n:>3} — {sebab}")
    return baris
