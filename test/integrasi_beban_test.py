"""
Beban dan pembayarannya, lewat endpoint sungguhan.

Yang dijaga di berkas ini satu hal: menghapus beban TIDAK boleh berhenti pada
dokumennya.

Pembayaran keluar yang melekat pada beban ikut terhitung pada saldo bank dan
pada kalender kas. Kalau bebannya terhapus sedangkan pembayarannya tidak,
yang tersisa adalah uang keluar tanpa dokumen: angkanya tetap mengurangi
saldo, tetapi tidak dapat ditelusuri ke beban mana pun — dan tidak ada
halaman mana pun yang menampilkannya, karena semua daftar menyaring lewat
dokumen induknya.

Uji statis tidak dapat membuktikan ini. Yang membuktikannya hanya membaca
baris pembayaran itu KEMBALI dari basis data sesudah bebannya dihapus.

Lihat `test/_integrasi.py` untuk cara menjalankannya.
"""

from datetime import date as d

import pytest

from _integrasi import (  # noqa: F401
    butuh_db,
    sambungan,
    klien,
    bersihkan,
    tanda,
)

pytestmark = butuh_db


async def _buat_beban(klien, bersihkan, keterangan: str) -> int:
    from models.expense_model import expenses_table

    r = await klien.post(
        "/expenses/",
        json={
            "invoiceName": keterangan,
            "receiptName": keterangan,
            "date": str(d.today()),
            "purchaseType": "Jasa",
            "dpp": 1_000_000,
            "ppn": 0,
            "pbbkb": 0,
            "pphPercentage": 0,
            "bankName": "Bank Uji",
            "bankAccountName": "Rekening Uji",
            "bankAccountNumber": "000",
            "paymentMethod": "Transfer",
            "description": keterangan,
        },
    )
    assert r.status_code == 200, r.text
    beban_id = r.json()["expense_id"]
    bersihkan(expenses_table, beban_id)
    return beban_id


async def _buat_pembayaran(klien, bersihkan, beban_id: int, nilai: int) -> int:
    """
    Pembayaran ditulis langsung ke tabelnya, bukan lewat endpoint.

    Yang diuji di berkas ini adalah PENGHAPUSAN beban; membuat pembayaran
    lewat endpointnya menyeret bank, saldo, dan penomoran ikut serta — dan
    kegagalan di salah satunya akan tampak seperti kegagalan uji ini, padahal
    bukan. Barisnya dibuat sesederhana mungkin, tepat seperti yang dilihat
    oleh kueri penghapusan.
    """
    from datetime import datetime as dt

    from utils.database import database
    from models.payment_outgoing_model import payments_outgoing_table

    pembayaran_id = await database.execute(
        payments_outgoing_table.insert().values(
            date=d.today(),
            amount=nilai,
            expenseID=beban_id,
            createdAt=dt.now(),
            createdBy=1,
            isDelete=False,
            isApprove=True,
            status="ready",
        )
    )
    bersihkan(payments_outgoing_table, pembayaran_id)
    return pembayaran_id


async def _baca_pembayaran(pembayaran_id: int):
    from utils.database import database
    from models.payment_outgoing_model import payments_outgoing_table

    return await database.fetch_one(
        payments_outgoing_table.select().where(
            payments_outgoing_table.c.id == pembayaran_id
        )
    )


# ----------------------------------------------------------------------
# Penghapusan sederhana
# ----------------------------------------------------------------------

async def test_beban_tanpa_pembayaran_boleh_dihapus(klien, bersihkan):
    """Yang belum pernah dibayar tidak punya alasan untuk ditahan."""
    t = tanda()
    beban_id = await _buat_beban(klien, bersihkan, f"Beban {t}")

    r = await klien.delete(f"/expenses/{beban_id}")
    assert r.status_code == 200, r.text


async def test_beban_tanpa_lawan_transaksi_tetap_terbaca(klien, bersihkan):
    """
    `opponentID` boleh kosong — dan beban seperti itu harus tetap dapat
    dibuka.

    Yang dulu terjadi: `get_by_id` menautkan `expense_opponents` dengan
    tautan biasa (INNER), sedangkan daftar bebannya memakai tautan kiri luar.
    Akibatnya beban tanpa lawan transaksi MUNCUL di daftar tetapi menjawab
    "Expense not found" begitu dibuka atau dihapus — dan pesan itu terdengar
    cukup benar untuk membuat yang membacanya menyimpulkan datanya hilang,
    bukan bahwa kuerinya yang menyembunyikan.

    Beban rutin seperti setoran pajak, BPJS, dan listrik memang tidak punya
    lawan transaksi.
    """
    t = tanda()
    beban_id = await _buat_beban(klien, bersihkan, f"Tanpa lawan {t}")

    r = await klien.get(f"/expenses/{beban_id}")
    assert r.status_code == 200, r.text


async def test_beban_yang_sudah_terhapus_ditolak(klien, bersihkan):
    """
    Penghapusan kedua harus berhenti dengan jelas, bukan menjawab berhasil.

    Menjawab berhasil pada dokumen yang sudah tidak ada membuat tombol yang
    tidak melakukan apa-apa tampak bekerja — dan menutupi kekeliruan di sisi
    pemanggilnya.
    """
    t = tanda()
    beban_id = await _buat_beban(klien, bersihkan, f"Beban {t}")

    assert (await klien.delete(f"/expenses/{beban_id}")).status_code == 200

    r = await klien.delete(f"/expenses/{beban_id}")
    assert r.status_code == 400, r.text


async def test_beban_terhapus_hilang_dari_pembacaan(klien, bersihkan):
    """
    Penghapusannya lunak (`isDelete`), jadi barisnya tetap ada di tabel.
    Yang harus berubah adalah apa yang dilihat pemakai.
    """
    from utils.database import database
    from models.expense_model import expenses_table

    t = tanda()
    beban_id = await _buat_beban(klien, bersihkan, f"Beban {t}")
    assert (await klien.delete(f"/expenses/{beban_id}")).status_code == 200

    baris = await database.fetch_one(
        expenses_table.select().where(expenses_table.c.id == beban_id)
    )
    assert baris is not None, "penghapusannya harus lunak, bukan keras"
    assert baris["isDelete"] is True or baris["isDelete"] == 1


# ----------------------------------------------------------------------
# Yang sebenarnya dijaga: pembayarannya ikut
# ----------------------------------------------------------------------

async def test_pembayaran_ikut_terhapus_saat_bebannya_dihapus(klien, bersihkan):
    """
    INI inti berkas ini.

    Sebelum perbaikan, `delete_expense` hanya menyentuh dokumennya. Pembayaran
    yang melekat tetap hidup DAN tetap `isApprove`, sehingga tetap ikut
    dihitung pada saldo bank dan muncul di kalender kas — sebagai uang keluar
    yang tidak punya dokumen induk lagi.

    Yang diperiksa di sini bukan jawaban endpointnya, melainkan baris
    pembayarannya sendiri, dibaca ulang dari basis data.
    """
    t = tanda()
    beban_id = await _buat_beban(klien, bersihkan, f"Beban {t}")
    pembayaran_id = await _buat_pembayaran(klien, bersihkan, beban_id, 1_000_000)

    sebelum = await _baca_pembayaran(pembayaran_id)
    assert sebelum["isDelete"] in (False, 0)

    r = await klien.delete(f"/expenses/{beban_id}")
    assert r.status_code == 200, r.text

    sesudah = await _baca_pembayaran(pembayaran_id)
    assert sesudah["isDelete"] in (True, 1), (
        "pembayaran tertinggal hidup setelah bebannya dihapus"
    )
    assert sesudah["isApprove"] in (False, 0), (
        "persetujuan pembayaran harus ikut dicabut; kalau tidak, uangnya "
        "tetap terhitung keluar"
    )


async def test_pembayaran_beban_lain_tidak_ikut_terhapus(klien, bersihkan):
    """
    Penghapusannya harus tepat sasaran.

    Kueri yang menyapu terlalu lebar — salah kolom, atau lupa `where` —
    menghapus pembayaran milik beban lain, dan kerusakannya jauh lebih
    mahal daripada yang diperbaikinya.
    """
    t = tanda()
    beban_a = await _buat_beban(klien, bersihkan, f"Beban A {t}")
    beban_b = await _buat_beban(klien, bersihkan, f"Beban B {t}")

    bayar_a = await _buat_pembayaran(klien, bersihkan, beban_a, 500_000)
    bayar_b = await _buat_pembayaran(klien, bersihkan, beban_b, 700_000)

    assert (await klien.delete(f"/expenses/{beban_a}")).status_code == 200

    assert (await _baca_pembayaran(bayar_a))["isDelete"] in (True, 1)
    assert (await _baca_pembayaran(bayar_b))["isDelete"] in (False, 0), (
        "pembayaran milik beban lain ikut terhapus"
    )


# ----------------------------------------------------------------------
# Penjaga level
# ----------------------------------------------------------------------

async def test_level_rendah_tidak_boleh_menghapus_beban_berpembayaran(
    klien, bersihkan
):
    """
    Menghapus beban berpembayaran berarti ikut MEMBATALKAN pembayaran —
    sesuatu yang di pintu lain hanya boleh dilakukan level 4 ke atas.
    Membiarkannya lewat pintu ini membuat penjaga di sana tidak ada artinya.

    Dipanggil di lapis controller karena yang diuji adalah keputusannya
    terhadap level, bukan cara level itu sampai ke sana — dan basis datanya
    tetap yang sungguhan.
    """
    from controllers.expense_controller import ExpenseController

    t = tanda()
    beban_id = await _buat_beban(klien, bersihkan, f"Beban {t}")
    pembayaran_id = await _buat_pembayaran(klien, bersihkan, beban_id, 250_000)

    hasil = await ExpenseController.delete_expense(beban_id, 1, userLevel=2)

    assert hasil.get("error") == "EXPENSE_HAS_PAYMENTS"
    assert hasil.get("status") == 409
    assert (await _baca_pembayaran(pembayaran_id))["isDelete"] in (False, 0)


async def test_level_rendah_tetap_boleh_menghapus_beban_tanpa_pembayaran(
    klien, bersihkan
):
    """
    Penjaganya tidak boleh kebablasan: yang ditahan adalah pembatalan
    pembayaran, bukan penghapusan beban itu sendiri.
    """
    from controllers.expense_controller import ExpenseController

    t = tanda()
    beban_id = await _buat_beban(klien, bersihkan, f"Beban {t}")

    hasil = await ExpenseController.delete_expense(beban_id, 1, userLevel=2)
    assert "error" not in hasil, hasil
