"""
Selisih kecil pada "selaraskan status lunas" ditanyakan, bukan diputuskan.

Kenapa
------

Ambang lima rupiah dibuat untuk menyerap pembulatan pajak, dan ia memang
perlu. Tetapi dipakai sebagai keputusan OTOMATIS, ia juga menelan selisih
pembulatan antar-pembukuan — selisih yang di AKN justru dicatat sebagai
pembayaran tersendiri bernilai di bawah satu rupiah.

Akibatnya berurutan: dokumen ditandai lunas begitu tombol selaraskan ditekan,
isyarat "masih kurang sedikit" hilang, dan pembayaran pembulatan itu tidak
pernah sempat dibuat karena tidak ada lagi yang menunjukkan bahwa ia kurang.

Sekarang tiga keadaan, bukan dua:

    selisih <= 0,01      lunas, tanpa bertanya
    0,01 < selisih <= 5  TANYAKAN dulu; tidak ada yang ditulis
    selisih > 5          belum lunas

Lapisan tengah itu yang baru. Jawabannya 200 dengan `butuh_konfirmasi`, bukan
galat: tidak ada yang keliru pada permintaannya, yang diperlukan keputusan.

Lihat `test/_integrasi.py` untuk cara menjalankannya.
"""

from datetime import date as d, datetime as dt

import pytest

from _integrasi import (  # noqa: F401
    butuh_db,
    sambungan,
    klien,
    bersihkan,
    tanda,
)

pytestmark = butuh_db


async def _buat_beban(klien, bersihkan, dpp: float) -> int:
    from models.expense_model import expenses_table

    t = tanda()
    r = await klien.post(
        "/expenses/",
        json={
            "invoiceName": t,
            "receiptName": t,
            "date": str(d.today()),
            "purchaseType": "Jasa",
            "dpp": dpp,
            "ppn": 0,
            "pbbkb": 0,
            "pphPercentage": 0,
            "bankName": "Bank Uji",
            "bankAccountName": "Rekening Uji",
            "bankAccountNumber": "000",
            "paymentMethod": "Transfer bank",
            "description": t,
        },
    )
    assert r.status_code == 200, r.text
    beban_id = r.json()["expense_id"]
    bersihkan(expenses_table, beban_id)
    return beban_id


async def _bayar_disetujui(bersihkan, beban_id: int, nominal: float) -> int:
    """
    Pembayaran ditulis langsung dan LANGSUNG disetujui.

    Yang diuji di sini keputusan status lunasnya, bukan alur persetujuan;
    lewat endpoint, uji ini akan ikut gagal setiap kali ada yang berubah
    pada penjaga persetujuan — dan kegagalannya menuduh tempat yang salah.
    """
    from utils.database import database
    from models.payment_outgoing_model import payments_outgoing_table

    pembayaran_id = await database.execute(
        payments_outgoing_table.insert().values(
            date=d.today(),
            amount=nominal,
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


async def _lunas(beban_id: int) -> bool:
    from utils.database import database
    from models.expense_model import expenses_table

    baris = await database.fetch_one(
        expenses_table.select().where(expenses_table.c.id == beban_id)
    )
    return bool(baris["isPaid"])


async def _selaraskan(klien, beban_id: int, konfirmasi: bool = False):
    return await klien.post(
        f"/outgoing-payments/selaraskan/expense/{beban_id}",
        params={"konfirmasi": str(konfirmasi).lower()},
    )


# ----------------------------------------------------------------------
# Lapisan tengah — yang diminta
# ----------------------------------------------------------------------

async def test_selisih_kecil_tidak_langsung_ditandai_lunas(klien, bersihkan):
    """
    Inti permintaannya: kurang Rp 0,83 tidak boleh langsung jadi lunas.

    Justru selisih inilah yang menjadi pembayaran pembulatan berikutnya; bila
    dokumennya sudah bertanda lunas, pembayaran itu tidak pernah dibuat.
    """
    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)
    await _bayar_disetujui(bersihkan, beban_id, 999_999.17)

    r = await _selaraskan(klien, beban_id)
    assert r.status_code == 200, r.text
    assert r.json()["butuh_konfirmasi"] is True
    assert not await _lunas(beban_id)


async def test_pertanyaannya_menyebut_angkanya(klien, bersihkan):
    """
    "Ada selisih" saja tidak dapat diputuskan siapa pun. Yang ditanya perlu
    melihat berapa nilai dokumennya, berapa yang sudah dibayar, dan berapa
    selisihnya — dan ketiganya harus datang dari perhitungan yang SAMA dengan
    yang menandai lunas, bukan dihitung ulang di layar.
    """
    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)
    await _bayar_disetujui(bersihkan, beban_id, 999_999.17)

    isi = (await _selaraskan(klien, beban_id)).json()
    assert isi["nilai"] == pytest.approx(1_000_000, abs=0.01)
    assert isi["dibayar"] == pytest.approx(999_999.17, abs=0.01)
    assert isi["selisih"] == pytest.approx(0.83, abs=0.01)


async def test_konfirmasi_menandainya_lunas(klien, bersihkan):
    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)
    await _bayar_disetujui(bersihkan, beban_id, 999_999.17)

    assert (await _selaraskan(klien, beban_id)).json()["butuh_konfirmasi"] is True
    assert not await _lunas(beban_id)

    r = await _selaraskan(klien, beban_id, konfirmasi=True)
    assert r.status_code == 200, r.text
    assert r.json()["butuh_konfirmasi"] is False
    assert await _lunas(beban_id)


async def test_pembayaran_pembulatan_menutupnya_tanpa_bertanya(klien, bersihkan):
    """
    Jalur yang sebenarnya dituju: selisihnya DICATAT, bukan dimaafkan.

    Setelah pembayaran pembulatan Rp 0,83 masuk, tidak ada lagi yang perlu
    ditanyakan — dan dokumennya menjadi lunas dengan angka yang benar-benar
    cocok, bukan dengan selisih yang ditutup toleransi.
    """
    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)
    await _bayar_disetujui(bersihkan, beban_id, 999_999.17)
    await _bayar_disetujui(bersihkan, beban_id, 0.83)

    r = await _selaraskan(klien, beban_id)
    assert r.json()["butuh_konfirmasi"] is False
    assert await _lunas(beban_id)


# ----------------------------------------------------------------------
# Dua lapisan lainnya tidak boleh ikut berubah
# ----------------------------------------------------------------------

async def test_cocok_persis_tetap_langsung_lunas(klien, bersihkan):
    """
    Yang tidak berselisih tidak boleh ikut ditanyai. Menanyakan yang sudah
    jelas membuat pertanyaannya berhenti dibaca.
    """
    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)
    await _bayar_disetujui(bersihkan, beban_id, 1_000_000)

    r = await _selaraskan(klien, beban_id)
    assert r.json()["butuh_konfirmasi"] is False
    assert await _lunas(beban_id)


async def test_selisih_satu_sen_masih_dianggap_nol(klien, bersihkan):
    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)
    await _bayar_disetujui(bersihkan, beban_id, 999_999.99)

    r = await _selaraskan(klien, beban_id)
    assert r.json()["butuh_konfirmasi"] is False
    assert await _lunas(beban_id)


async def test_selisih_besar_tetap_belum_lunas_tanpa_ditanya(klien, bersihkan):
    """
    Kekurangan bayar sungguhan bukan bahan pertanyaan — ia jawaban.
    Menawarkan "mau tandai lunas?" atas kekurangan satu juta rupiah membuat
    pertanyaannya berbahaya.
    """
    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)
    await _bayar_disetujui(bersihkan, beban_id, 900_000)

    r = await _selaraskan(klien, beban_id)
    assert r.json()["butuh_konfirmasi"] is False
    assert r.json()["lunas"] is False
    assert not await _lunas(beban_id)


async def test_selisih_tepat_lima_rupiah_masih_ditanyakan(klien, bersihkan):
    """Batas atasnya ikut ditanyakan, bukan jatuh ke "belum lunas"."""
    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)
    await _bayar_disetujui(bersihkan, beban_id, 999_995)

    assert (await _selaraskan(klien, beban_id)).json()["butuh_konfirmasi"] is True


# ----------------------------------------------------------------------
# Jalur OTOMATIS — saat tidak ada yang dapat ditanyai
# ----------------------------------------------------------------------

async def test_penyelarasan_otomatis_tidak_memutuskan_sendiri(klien, bersihkan):
    """
    Penyelarasan otomatis berjalan sesudah pembayaran disetujui atau dihapus,
    saat tidak ada siapa pun yang dapat ditanyai.

    Menandai lunas di sana berarti memutuskan diam-diam — dan menghilangkan
    isyarat yang justru diperlukan. Karena itu statusnya dibiarkan apa adanya
    sampai ada yang melihat dan memutuskan.
    """
    from controllers.payment_outgoing_controller import PaymentOutgoingController

    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)
    await _bayar_disetujui(bersihkan, beban_id, 999_999.17)

    class _Sasaran:
        purchaseID = None
        reimbursementID = None
        expenseID = beban_id
        salarySlipID = None
        loanID = None

    hasil = await PaymentOutgoingController.selaraskan_status_lunas(
        _Sasaran(), 1
    )

    assert hasil["butuh_konfirmasi"] is True
    assert not await _lunas(beban_id)


async def test_penyelarasan_otomatis_tetap_mencabut_yang_jelas_kurang(
    klien, bersihkan
):
    """
    Yang tidak diputuskan sendiri hanya lapisan TENGAH. Kekurangan bayar yang
    jelas tetap harus mencabut status lunas tanpa menunggu siapa pun —
    dokumen bertanda lunas yang uangnya tidak keluar jauh lebih mahal.
    """
    from utils.database import database
    from models.expense_model import expenses_table
    from controllers.payment_outgoing_controller import PaymentOutgoingController

    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)
    await database.execute(
        expenses_table.update()
        .where(expenses_table.c.id == beban_id)
        .values(isPaid=True)
    )

    class _Sasaran:
        purchaseID = None
        reimbursementID = None
        expenseID = beban_id
        salarySlipID = None
        loanID = None

    await PaymentOutgoingController.selaraskan_status_lunas(_Sasaran(), 1)
    assert not await _lunas(beban_id)


# ----------------------------------------------------------------------
# Pembayaran pembulatan harus dapat dibuat
# ----------------------------------------------------------------------

async def test_pembayaran_pembulatan_di_bawah_satu_rupiah_diterima(
    klien, bersihkan
):
    """
    Tanpa ini seluruh perubahan di atas tidak ada gunanya.

    Penjaga "sudah lunas" dulu menolak setiap pembayaran atas dokumen yang
    sisanya di bawah lima rupiah — persis pembayaran pembulatan yang hendak
    dicatat. Sisanya sekarang dinilai dengan ambang satu sen.
    """
    from models.payment_outgoing_model import payments_outgoing_table

    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)
    await _bayar_disetujui(bersihkan, beban_id, 999_999.17)

    r = await klien.post(
        "/outgoing-payments/",
        json={
            "purchaseID": None,
            "expenseID": beban_id,
            "reimbursementID": None,
            "salarySlipID": None,
            "date": str(d.today()),
            "amount": 0.83,
            "bankAccountID": None,
            "status": "ready",
        },
    )
    assert r.status_code == 200, r.text
    pid = r.json().get("payment_id")
    if pid:
        bersihkan(payments_outgoing_table, pid)
