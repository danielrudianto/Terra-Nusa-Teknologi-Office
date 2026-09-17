"""
Penggulungan balik transaksi — diuji terhadap MySQL SUNGGUHAN.

KENAPA HARUS MYSQL SUNGGUHAN

`test/_fake_db.py` menyediakan `transaction()` tiruan yang MENCATAT
pemanggilannya tetapi tidak menggulung balik apa pun — memang tidak ada basis
data di baliknya. Dengan tiruan itu, uji "apakah transaksinya dipakai" akan
hijau untuk kode yang tetap menyimpan penulisan separuh jadi.

Jadi berkas ini menulis ke basis data sungguhan, lalu MENGHITUNG BARISNYA.
Itu satu-satunya pertanyaan yang jawabannya berarti.

YANG DIJAGA

  1. Pengecualian di tengah membatalkan penulisan sebelumnya.
  2. Nilai kembalian ber-`error` JUGA membatalkannya. Ini yang paling mudah
     luput: controller di repo ini menandai gagal dengan `return {"error":
     ...}`, bukan `raise`, dan transaksi hanya digulung balik oleh
     PENGECUALIAN. Membungkus dengan `async with database.transaction():`
     polos menghasilkan kode yang terlihat aman dan tetap commit.
  3. Jalur berhasil tetap tersimpan — penjaga yang membatalkan segalanya juga
     "lulus" uji nomor 1 dan 2.
  4. Transaksi bersarang tidak saling menjatuhkan (repository CoP sudah punya
     transaksinya sendiri).

Cara menjalankan — lihat `test/_integrasi.py`:

    TEST_TANPA_MEILI=1 TEST_DATABASE_URL="mysql://..." \\
        ./env/bin/python -m pytest test/integrasi_transaksi_test.py -q
"""

import pytest

from _integrasi import butuh_db, sambungan  # noqa: F401

from utils.transaksi import atomik, gagal

pytestmark = butuh_db

TABEL = "uji_transaksi_atomik"


@pytest.fixture
async def tabel(sambungan):
    """
    Tabel coba-coba milik berkas ini sendiri.

    Sengaja TIDAK memakai tabel aplikasi: uji ini menghitung baris, dan
    menghitung baris di tabel yang dipakai orang lain berarti hasilnya
    bergantung pada apa yang kebetulan ada di sana.

    `ENGINE=InnoDB` disebut TERANG-TERANGAN. Pada MyISAM tidak ada transaksi
    sama sekali — penulisannya langsung jadi, `ROLLBACK` diabaikan dalam
    diam, dan seluruh berkas ini akan merah tanpa ada yang salah pada kode
    yang diujinya.
    """
    await sambungan.execute(f"DROP TABLE IF EXISTS {TABEL}")
    await sambungan.execute(
        f"CREATE TABLE {TABEL} ("
        " id INT PRIMARY KEY AUTO_INCREMENT,"
        " nama VARCHAR(40) NOT NULL"
        ") ENGINE=InnoDB"
    )
    try:
        yield sambungan
    finally:
        await sambungan.execute(f"DROP TABLE IF EXISTS {TABEL}")


async def _jumlah(db) -> int:
    return await db.fetch_val(f"SELECT COUNT(*) FROM {TABEL}")


async def _tulis(db, nama: str) -> None:
    await db.execute(f"INSERT INTO {TABEL} (nama) VALUES (:n)", {"n": nama})


# ---------------------------------------------------------------------------
# 1. Pengecualian
# ---------------------------------------------------------------------------


async def test_pengecualian_membatalkan_penulisan_sebelumnya(tabel):
    """
    Bentuk kegagalan yang sesungguhnya terjadi di produksi.

    Menyetujui pembayaran menulis status pembayarannya, lalu — terpisah —
    status lunas pembeliannya. Bila yang kedua melempar, yang pertama sudah
    tersimpan dan tidak ada apa pun yang menariknya kembali.
    """

    @atomik
    async def dua_tulis(db):
        await _tulis(db, "pembayaran")
        raise RuntimeError("penulisan kedua gagal")

    with pytest.raises(RuntimeError):
        await dua_tulis(tabel)

    assert await _jumlah(tabel) == 0, (
        "penulisan pertama tetap tersimpan — inilah pembayaran yang tercatat "
        "disetujui di atas pembelian yang tidak lunas"
    )


async def test_http_exception_juga_membatalkan(tabel):
    """
    `HTTPException` dipakai beberapa controller untuk menolak di tengah jalan.

    Ia pengecualian biasa, jadi seharusnya ikut membatalkan — tetapi karena
    ia bagian dari alur yang "normal" dan bukan tanda kerusakan, ia mudah
    dikira tidak perlu dijaga.
    """
    from fastapi import HTTPException

    @atomik
    async def tolak(db):
        await _tulis(db, "separuh")
        raise HTTPException(status_code=403, detail="tidak boleh")

    with pytest.raises(HTTPException):
        await tolak(tabel)

    assert await _jumlah(tabel) == 0


# ---------------------------------------------------------------------------
# 2. Nilai kembalian ber-`error` — yang paling mudah luput
# ---------------------------------------------------------------------------


async def test_kembalian_error_membatalkan_penulisan(tabel):
    """
    INTI SELURUH BERKAS INI.

    Controller menandai kegagalan dengan MENGEMBALIKAN dict, bukan melempar.
    Transaksi hanya digulung balik oleh pengecualian, jadi `return` biasa
    akan COMMIT — dan kode yang dibungkus `async with database.transaction():`
    polos akan terlihat aman sambil menyimpan penulisan separuh jadi persis
    seperti sebelum dibungkus.
    """

    @atomik
    async def gagal_dengan_dict(db):
        await _tulis(db, "pembayaran")
        return {"error": "pembeliannya sudah terhapus", "status": 400}

    hasil = await gagal_dengan_dict(tabel)

    assert gagal(hasil), "dict galatnya harus tetap sampai ke pemanggil"
    assert hasil["status"] == 400, "bentuk jawabannya tidak boleh berubah"
    assert await _jumlah(tabel) == 0, (
        "`return {'error': ...}` tidak membatalkan apa pun — transaksi polos "
        "akan COMMIT di sini, dan itu persis celah yang ditutup `@atomik`"
    )


async def test_pembungkus_polos_MEMANG_tidak_cukup(tabel):
    """
    Pembandingnya, supaya alasan `@atomik` ada tidak perlu dipercaya begitu saja.

    Yang di bawah ini adalah cara "wajar" membungkus transaksi. Ia menyimpan
    barisnya. Uji ini akan merah justru bila suatu saat `databases` mulai
    menggulung balik pada `return` biasa — dan kalau itu terjadi, `@atomik`
    boleh disederhanakan.
    """

    async def polos(db):
        async with db.transaction():
            await _tulis(db, "tersimpan diam-diam")
            return {"error": "gagal", "status": 400}

    await polos(tabel)

    assert await _jumlah(tabel) == 1, (
        "ternyata transaksi polos SUDAH membatalkan pada `return` — `@atomik` "
        "boleh disederhanakan"
    )


# ---------------------------------------------------------------------------
# 3. Jalur berhasil
# ---------------------------------------------------------------------------


async def test_jalur_berhasil_tetap_tersimpan(tabel):
    """
    Penjaga yang membatalkan SEGALANYA juga lulus kedua uji di atas.

    Tanpa uji ini, `@atomik` yang keliru — misalnya menganggap semua
    kembalian sebagai kegagalan — akan terlihat sempurna.
    """

    @atomik
    async def berhasil(db):
        await _tulis(db, "satu")
        await _tulis(db, "dua")
        return {"message": "ok", "id": 1}

    hasil = await berhasil(tabel)

    assert hasil["message"] == "ok"
    assert await _jumlah(tabel) == 2


async def test_kembalian_bukan_dict_tidak_dianggap_gagal(tabel):
    """
    Beberapa fungsi mengembalikan daftar, angka, atau `None`.

    Kalau `gagal()` salah menilai bentuk-bentuk itu, tindakan yang berhasil
    akan digulung balik tanpa satu pun pesan galat — kelas kegagalan yang
    paling sulit ditelusuri: tombolnya ditekan, tidak ada yang merah, dan
    datanya tidak ada.
    """

    @atomik
    async def kembalikan(db, nilai):
        await _tulis(db, "baris")
        return nilai

    for nilai in (None, 0, [], "", {"message": "ok"}):
        await sambungan_kosongkan(tabel)
        await kembalikan(tabel, nilai)
        assert await _jumlah(tabel) == 1, f"kembalian {nilai!r} dikira kegagalan"


async def sambungan_kosongkan(db) -> None:
    await db.execute(f"DELETE FROM {TABEL}")


# ---------------------------------------------------------------------------
# 4. Bersarang
# ---------------------------------------------------------------------------


async def test_transaksi_bersarang_ikut_dibatalkan(tabel):
    """
    Repository CoP sudah punya transaksinya sendiri.

    `databases` memakai SAVEPOINT untuk yang di dalam. Yang dijaga di sini:
    membungkus controller-nya dengan `@atomik` tidak membuat yang di dalam
    berhenti bekerja, DAN kegagalan di luar tetap menarik yang di dalam.
    """

    @atomik
    async def luar(db):
        async with db.transaction():
            await _tulis(db, "dari dalam")
        await _tulis(db, "dari luar")
        return {"error": "gagal sesudah keduanya", "status": 500}

    await luar(tabel)

    assert await _jumlah(tabel) == 0, (
        "penulisan di dalam transaksi bersarang selamat dari pembatalan di "
        "luar — satu tindakan terbelah jadi dua nasib"
    )


# ---------------------------------------------------------------------------
# 5. Cabang "tanpa sambungan" bukan lubang
# ---------------------------------------------------------------------------


async def test_saat_tersambung_transaksi_BENAR_BENAR_dibuka(tabel):
    """
    `@atomik` melewati pembungkusan bila basis datanya tidak tersambung.

    Cabang itu ada demi pengujian unit yang menambal lapis repository — tidak
    ada SQL yang jalan di sana, jadi tidak ada yang perlu digulung balik. Tapi
    cabang semacam itu adalah cara paling rapi untuk MEMATIKAN sebuah penjaga
    tanpa ada yang sadar: seandainya `is_connected` suatu saat menjawab salah,
    seluruh perlindungan ini lenyap tanpa satu pun uji berubah warna.

    Karena itu yang diuji di sini keadaan SEBALIKNYA — saat sambungannya ada,
    pembungkusannya benar-benar terjadi.
    """
    assert tabel.is_connected, "prasyarat: fixture ini menyambungkan basis data"

    @atomik
    async def gagal_dengan_dict(db):
        await _tulis(db, "harus batal")
        return {"error": "gagal", "status": 400}

    await gagal_dengan_dict(tabel)

    assert await _jumlah(tabel) == 0, (
        "sambungannya ada tetapi penulisannya tetap tersimpan — `@atomik` "
        "mengambil cabang 'tanpa sambungan' padahal tidak seharusnya"
    )
