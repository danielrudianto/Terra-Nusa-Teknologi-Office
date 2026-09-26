"""
Penguncian optimistik — diuji terhadap MySQL SUNGGUHAN.

KENAPA HARUS MYSQL SUNGGUHAN

Seluruh mekanisme ini bertumpu pada satu perilaku basis data: berapa baris yang
dilaporkan terpengaruh oleh `UPDATE`. Tiruan di `test/_fake_db.py` mengembalikan
apa pun yang diantrikan pengujinya, jadi dengan tiruan, uji ini akan hijau untuk
kode yang tidak menjaga apa-apa.

Dan perilakunya memang berlapis: MySQL secara bawaan menghitung baris yang
BERUBAH, bukan yang cocok. Yang membuat hitungannya dapat dipercaya adalah
`rowVersion` yang selalu bertambah — kalau baris itu suatu saat berhenti
bertambah, penjagaannya runtuh tanpa satu pun uji berubah warna, kecuali uji
yang benar-benar menghitung baris di basis data sungguhan.

SKENARIO YANG DIJAGA

Inilah kejadiannya, persis:

    Ani  membuka CoP #7  (versi 0)
    Budi membuka CoP #7  (versi 0)
    Ani  menyimpan       -> versi menjadi 1
    Budi menyimpan       -> HARUS DITOLAK, bukan menimpa pekerjaan Ani

Cara menjalankan — lihat `test/_integrasi.py`:

    TEST_TANPA_MEILI=1 TEST_DATABASE_URL="mysql://..." \\
        ./env/bin/python -m pytest test/integrasi_kunci_optimistik_test.py -q
"""

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, select

from _integrasi import butuh_db, sambungan  # noqa: F401

from utils.kunci_optimistik import jawaban_konflik, perbarui_terkunci

pytestmark = butuh_db

TABEL_NAMA = "uji_kunci_optimistik"

_md = MetaData()
TABEL = Table(
    TABEL_NAMA,
    _md,
    Column("id", Integer, primary_key=True),
    Column("catatan", String(80)),
    Column("rowVersion", Integer),
)


@pytest.fixture
async def dokumen(sambungan):
    """
    Satu baris contoh, pada tabel milik berkas ini sendiri.

    `ENGINE=InnoDB` disebut terang-terangan — sama seperti pada uji transaksi,
    karena tabel MyISAM akan membuat seluruh berkas ini merah untuk sebab yang
    tidak ada hubungannya dengan kode yang diuji.
    """
    await sambungan.execute(f"DROP TABLE IF EXISTS {TABEL_NAMA}")
    await sambungan.execute(
        f"CREATE TABLE {TABEL_NAMA} ("
        " id INT PRIMARY KEY AUTO_INCREMENT,"
        " catatan VARCHAR(80),"
        " rowVersion INT NOT NULL DEFAULT 0"
        ") ENGINE=InnoDB"
    )
    await sambungan.execute(
        f"INSERT INTO {TABEL_NAMA} (id, catatan, rowVersion) VALUES (7, 'asli', 0)"
    )
    try:
        yield sambungan
    finally:
        await sambungan.execute(f"DROP TABLE IF EXISTS {TABEL_NAMA}")


async def _baca(db):
    return await db.fetch_one(select(TABEL).where(TABEL.c.id == 7))


# ---------------------------------------------------------------------------
# Skenario yang sebenarnya terjadi
# ---------------------------------------------------------------------------


async def test_penyimpanan_kedua_DITOLAK_bukan_menimpa(dokumen):
    """
    Inti seluruh berkas ini.

    Ani dan Budi sama-sama membuka versi 0. Ani menyimpan lebih dulu. Simpanan
    Budi dibangun di atas keadaan yang sudah tidak berlaku, dan harus ditolak —
    bukan diam-diam menghapus pekerjaan Ani.
    """
    versi_ani = 0
    versi_budi = 0  # keduanya membuka layar yang sama

    assert await perbarui_terkunci(TABEL, 7, {"catatan": "tulisan Ani"}, versi_ani) == "tersimpan"

    hasil_budi = await perbarui_terkunci(TABEL, 7, {"catatan": "tulisan Budi"}, versi_budi)

    assert hasil_budi == "konflik", (
        "simpanan Budi diterima — pekerjaan Ani tertimpa tanpa jejak apa pun, "
        "dan inilah kegagalan yang seluruh berkas ini ada untuk mencegahnya"
    )

    baris = await _baca(dokumen)
    assert baris["catatan"] == "tulisan Ani"
    assert baris["rowVersion"] == 1, "versinya harus bertambah TEPAT satu kali"


async def test_budi_berhasil_setelah_memuat_ulang(dokumen):
    """
    Penjaga yang menolak SEGALANYA juga lulus uji di atas.

    Sesudah memuat ulang dan mendapat versi terbaru, simpanan Budi harus
    masuk — kalau tidak, yang kita pasang bukan penjaga melainkan penghalang.
    """
    await perbarui_terkunci(TABEL, 7, {"catatan": "tulisan Ani"}, 0)

    versi_baru = (await _baca(dokumen))["rowVersion"]
    hasil = await perbarui_terkunci(TABEL, 7, {"catatan": "tulisan Budi"}, versi_baru)

    assert hasil == "tersimpan"
    assert (await _baca(dokumen))["catatan"] == "tulisan Budi"


# ---------------------------------------------------------------------------
# Tiga hasil, bukan dua
# ---------------------------------------------------------------------------


async def test_baris_yang_tidak_ada_dibedakan_dari_konflik(dokumen):
    """
    Keduanya sama-sama menghasilkan nol baris terpengaruh.

    Menjawabnya dengan pesan yang sama membuat yang membacanya mencari di
    tempat yang salah: "sudah diubah orang lain" untuk dokumen yang sebenarnya
    sudah terhapus mengirim orang memuat ulang halaman yang tidak akan pernah
    memuat apa pun.
    """
    assert await perbarui_terkunci(TABEL, 999, {"catatan": "x"}, 0) == "hilang"


# ---------------------------------------------------------------------------
# Hitungan baris yang dapat dipercaya
# ---------------------------------------------------------------------------


async def test_menyimpan_TANPA_perubahan_tetap_dihitung_tersimpan(dokumen):
    """
    Cacat yang sudah ada di `expense.update`, ikut tertutup di sini.

    Secara bawaan MySQL menghitung baris yang BERUBAH. Menyimpan formulir tanpa
    mengubah satu nilai pun karena itu menghasilkan nol — dan kode yang ada
    menerjemahkannya menjadi "Expense not found" untuk data yang jelas-jelas
    ada di layar orang yang menekan Simpan.

    `rowVersion` yang selalu bertambah membuat barisnya selalu berubah, jadi
    nol kembali hanya berarti satu hal.
    """
    hasil = await perbarui_terkunci(TABEL, 7, {"catatan": "asli"}, 0)

    assert hasil == "tersimpan", (
        "penyimpanan tanpa perubahan dilaporkan gagal — MySQL menghitung baris "
        "yang BERUBAH, dan tanpa kenaikan versi hitungannya nol"
    )
    assert (await _baca(dokumen))["rowVersion"] == 1


async def test_versi_tidak_dapat_dipaksa_dari_muatan(dokumen):
    """
    `rowVersion` di dalam muatan permintaan harus DIABAIKAN.

    Kalau tidak, siapa pun dapat mengirim `rowVersion: 999` dan mematikan
    penjagaan ini untuk dirinya sendiri — penjaga yang dapat dimatikan oleh
    yang dijaganya bukan penjaga.

    TERUS TERANG: uji ini HIJAU dengan atau tanpa baris `nilai_baru.pop(...)`
    di `perbarui_terkunci`. Saya mencobanya — melepas baris itu tidak membuat
    satu pun uji di berkas ini merah, karena penetapan `nilai_baru[KOLOM_VERSI]
    = ... + 1` tepat di bawahnya sudah menimpa apa pun yang datang dari
    muatan.

    Jadi uji ini tidak menjaga baris itu; ia menjaga AKIBATNYA — bahwa versi
    yang dikirim pemanggil tidak pernah menjadi versi yang tersimpan. `pop`
    tetap ditulis sebagai lapis kedua: bila urutan kedua baris itu suatu saat
    tertukar, yang menyisakan perlindungan hanyalah dia.
    """
    await perbarui_terkunci(TABEL, 7, {"catatan": "a", "rowVersion": 999}, 0)

    assert (await _baca(dokumen))["rowVersion"] == 1, (
        "versinya diambil dari muatan permintaan, bukan dari basis data"
    )


# ---------------------------------------------------------------------------
# Jalur tanpa versi
# ---------------------------------------------------------------------------


async def test_tanpa_versi_tetap_tersimpan_dan_menaikkan_versi(dokumen):
    """
    Jalur sementara untuk jeda antara deploy backend dan frontend.

    Selama frontend belum mengirim `rowVersion`, penyimpanannya harus berjalan
    seperti sebelumnya — kalau tidak, seluruh penyuntingan berhenti pada jeda
    di antara kedua deploy, dan penjaga yang dipasang untuk melindungi data
    justru menghentikan pekerjaan semua orang.
    """
    assert await perbarui_terkunci(TABEL, 7, {"catatan": "tanpa versi"}, None) == "tersimpan"

    baris = await _baca(dokumen)
    assert baris["catatan"] == "tanpa versi"
    assert baris["rowVersion"] == 1, (
        "versinya tidak bertambah pada jalur tanpa versi — yang membaca "
        "berikutnya akan memegang versi basi sejak awal"
    )


# ---------------------------------------------------------------------------
# Jawaban ke pengguna
# ---------------------------------------------------------------------------


def test_jawaban_konflik_memakai_409_dan_menyebut_langkahnya():
    """
    409, bukan 400 atau 500.

    Ini bukan permintaan yang salah bentuk dan bukan kerusakan; ini keadaan
    yang sah dan dapat dipulihkan. Kodenya harus mengatakan begitu supaya
    frontend dapat menanganinya secara khusus, bukan menampilkan "terjadi
    kesalahan" seperti galat lainnya.
    """
    j = jawaban_konflik("Certificate of payment")

    assert j["status"] == 409
    assert "Certificate of payment" in j["error"]
    assert "Muat ulang" in j["error"], (
        "pesannya tidak menyebutkan langkah berikutnya — yang membacanya tahu "
        "ada yang salah tetapi tidak tahu harus berbuat apa"
    )
