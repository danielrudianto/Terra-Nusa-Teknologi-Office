"""
Penghitung kueri per permintaan.

KENAPA INI DIUJI

Alat ukur yang salah lebih buruk daripada tidak ada alat ukur. Kalau
penghitungnya diam-diam melewatkan `execute`, permintaan yang menulis ratusan
baris satu per satu akan terlihat sebagai `X-Db-Queries: 0` — dan yang
membacanya akan menyimpulkan basis datanya bukan penyebabnya, lalu mencari di
tempat yang salah.

Yang dijaga di sini tiga hal yang tidak menghasilkan galat bila rusak:

  1. SETIAP method yang menyentuh basis data ikut terhitung.
  2. Kueri yang GAGAL tetap terhitung — yang lambat LALU gagal (misalnya
     kehabisan waktu tunggu) adalah gejala yang paling perlu terlihat.
  3. Di luar permintaan HTTP, penghitungnya tidak melempar apa pun.
"""

import pytest
from databases import Database

from utils import db_ukur
from utils.db_ukur import DatabaseTerukur, mulai_ukur


class _Palsu(DatabaseTerukur):
    """`DatabaseTerukur` yang induknya diganti agar tidak menyentuh MySQL."""

    def __init__(self):
        # Sengaja TIDAK memanggil `Database.__init__`: ia mengurai URL dan
        # menyiapkan backend, dan tidak satu pun dibutuhkan di sini.
        self.dipanggil: list[str] = []


async def _stub(self, *a, **k):
    return "hasil"


async def _stub_gagal(self, *a, **k):
    raise RuntimeError("kueri gagal")


METHOD = ["fetch_all", "fetch_one", "fetch_val", "execute", "execute_many"]


@pytest.mark.parametrize("nama", METHOD)
async def test_setiap_method_terhitung(monkeypatch, nama):
    """
    Satu method yang terlewat berarti seluruh angkanya menyesatkan.

    Diuji per method, bukan sekali untuk semuanya: kalau hanya `fetch_all`
    yang diperiksa, `execute` dapat lepas dari pembungkusnya tanpa ada uji
    yang merah — dan halaman yang MENULIS banyak baris justru yang paling
    sering jadi sebab keluhan lambat.
    """
    monkeypatch.setattr(Database, nama, _stub, raising=False)
    wadah = mulai_ukur()
    db = _Palsu()

    await getattr(db, nama)("SELECT 1")

    assert wadah["n"] == 1, f"`{nama}` tidak terhitung"
    assert wadah["ms"] >= 0


@pytest.mark.parametrize("nama", METHOD)
async def test_kueri_gagal_tetap_terhitung(monkeypatch, nama):
    """
    Yang lambat LALU gagal adalah gejala yang paling perlu terlihat.

    Bila hitungannya hanya bertambah pada keberhasilan, permintaan yang
    kehabisan waktu tunggu tercatat sebagai nol kueri — dan yang membacanya
    menyimpulkan basis datanya tidak tersentuh sama sekali.
    """
    monkeypatch.setattr(Database, nama, _stub_gagal, raising=False)
    wadah = mulai_ukur()
    db = _Palsu()

    with pytest.raises(RuntimeError):
        await getattr(db, nama)("SELECT 1")

    assert wadah["n"] == 1, f"`{nama}` yang gagal tidak terhitung"


async def test_hitungan_menumpuk_dalam_satu_permintaan(monkeypatch):
    """N+1 hanya terbaca kalau penambahannya benar-benar menumpuk."""
    monkeypatch.setattr(Database, "fetch_one", _stub, raising=False)
    wadah = mulai_ukur()
    db = _Palsu()

    for _ in range(50):
        await db.fetch_one("SELECT 1")

    assert wadah["n"] == 50


async def test_di_luar_permintaan_tidak_melempar(monkeypatch):
    """
    Tugas latar, skrip, dan uji berjalan tanpa wadah hitungan.

    Itu jalur yang sah, bukan kelalaian — dan alat ukur yang menjatuhkan tugas
    latar hanya karena tidak ada permintaan HTTP adalah alat ukur yang menjadi
    sumber masalahnya sendiri.
    """
    monkeypatch.setattr(Database, "fetch_all", _stub, raising=False)
    db_ukur._ukuran.set(None)
    db = _Palsu()

    assert await db.fetch_all("SELECT 1") == "hasil"


async def test_wadah_baru_tiap_permintaan(monkeypatch):
    """
    Dua permintaan tidak boleh saling menambahi.

    `mulai_ukur()` dipanggil middleware pada setiap permintaan; kalau ia
    mengembalikan wadah yang sama, angka permintaan kedua sudah membawa sisa
    yang pertama dan halaman yang ringan terlihat berat.
    """
    monkeypatch.setattr(Database, "fetch_all", _stub, raising=False)
    db = _Palsu()

    pertama = mulai_ukur()
    await db.fetch_all("SELECT 1")

    kedua = mulai_ukur()
    await db.fetch_all("SELECT 1")

    assert pertama is not kedua
    assert pertama["n"] == 1
    assert kedua["n"] == 1
