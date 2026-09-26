"""
Membaca keluarga sebuah proyek: induknya dan anak-anaknya.

MENGAPA LAYAR MEMERLUKANNYA

Sebagian pekerjaan dipecah menjadi beberapa kode proyek: satu memegang
kontraknya, yang lain menampung biaya per paket. Dilihat sendiri-sendiri
keduanya tampak ganjil — ada proyek berpenjualan tanpa satu pun pembelian,
dan ada proyek berpembelian tanpa satu pun penjualan. Yang membukanya
menyimpulkan datanya rusak, padahal pasangannya ada di proyek sebelah.

YANG DIJAGA DI SINI

Proyek yang DIHAPUS tidak boleh ikut terbaca — baik sebagai anak maupun
sebagai induk. Anak yang dihapus tetap membawa `parentProjectID` di
barisnya; membacanya tanpa menyaring `isDelete` menampilkan proyek yang
sudah tidak ada lagi, lengkap dengan tautan yang menuju halaman kosong.
"""

import pytest

from repository.project_repository import ProjectRepository

MODUL = "repository.project_repository"


def _kolom_disaring(kueri: str) -> bool:
    """Kuerinya menyaring baris yang sudah dihapus."""
    teks = str(kueri).replace("\n", " ")
    return "isDelete" in teks


@pytest.mark.asyncio
async def test_anak_dibaca_beserta_kodenya(fake_db):
    db = fake_db(MODUL)
    db.queue(
        "fetch_all",
        [
            {"id": 2, "code": "R501A", "name": "Paket A", "isActive": 1,
             "isCancelled": 0, "isRetention": 0},
            {"id": 3, "code": "R501B", "name": "Paket B", "isActive": 1,
             "isCancelled": 0, "isRetention": 0},
        ],
    )
    db.queue("fetch_val", None)  # tidak punya induk

    hasil = await ProjectRepository.keluarga(1)

    assert hasil["induk"] is None
    assert [a["code"] for a in hasil["anak"]] == ["R501A", "R501B"]


@pytest.mark.asyncio
async def test_induk_dibaca_bila_proyek_ini_anak(fake_db):
    db = fake_db(MODUL)
    db.queue("fetch_all", [])
    db.queue("fetch_val", 7)
    db.queue(
        "fetch_one",
        {"id": 7, "code": "R501", "name": "Induk", "isActive": 1,
         "isCancelled": 0, "isRetention": 0},
    )

    hasil = await ProjectRepository.keluarga(2)

    assert hasil["anak"] == []
    assert hasil["induk"]["code"] == "R501"


@pytest.mark.asyncio
async def test_proyek_berdiri_sendiri_mengembalikan_kosong(fake_db):
    """
    Bukan galat, dan bukan pula `None`.

    Hampir SELURUH proyek berdiri sendiri. Bentuk balikan yang berbeda untuk
    keadaan yang paling lazim memaksa layar memeriksanya lebih dulu — dan
    yang lupa memeriksanya melihat galat pada proyek yang sama sekali tidak
    bermasalah.
    """
    db = fake_db(MODUL)
    db.queue("fetch_all", [])
    db.queue("fetch_val", None)

    hasil = await ProjectRepository.keluarga(9)

    assert hasil == {"induk": None, "anak": []}


@pytest.mark.asyncio
async def test_yang_sudah_dihapus_tidak_ikut(fake_db):
    """
    Penyaringnya harus ada di KEDUA kueri.

    Anak yang dihapus tetap membawa `parentProjectID`; induk yang dihapus
    tetap dirujuk anaknya. Keduanya menghasilkan tautan menuju halaman yang
    tidak ada isinya.
    """
    db = fake_db(MODUL)
    db.queue("fetch_all", [])
    db.queue("fetch_val", 7)
    db.queue("fetch_one", None)

    await ProjectRepository.keluarga(2)

    kueri = [q for m, q in db.calls if m in ("fetch_all", "fetch_one")]
    assert kueri, "tidak ada kueri yang dijalankan"
    for q in kueri:
        assert _kolom_disaring(q), f"kueri tanpa penyaring isDelete: {q}"


@pytest.mark.asyncio
async def test_induk_yang_sudah_dihapus_terbaca_kosong(fake_db):
    """Tautannya hilang, bukan menuju halaman kosong."""
    db = fake_db(MODUL)
    db.queue("fetch_all", [])
    db.queue("fetch_val", 7)
    db.queue("fetch_one", None)

    hasil = await ProjectRepository.keluarga(2)

    assert hasil["induk"] is None


@pytest.mark.asyncio
async def test_anak_diurutkan_menurut_kode(fake_db):
    """
    Urutan tetap, bukan urutan penyisipan.

    Keluarga proyek dibaca berulang kali oleh orang yang membandingkan
    isinya; urutan yang berubah-ubah membuat baris yang sama tampak berpindah
    tempat setiap kali layarnya dibuka.
    """
    db = fake_db(MODUL)
    db.queue("fetch_all", [])
    db.queue("fetch_val", None)

    await ProjectRepository.keluarga(1)

    kueri = str(db.calls[0][1]).replace("\n", " ")
    assert "ORDER BY" in kueri and "code" in kueri
