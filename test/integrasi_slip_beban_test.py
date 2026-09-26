"""
Membuat beban sekaligus slip pembayarannya, lewat endpoint sungguhan.

Kegagalan yang ditutup di sini persis yang dilaporkan: beban tersimpan, tetapi
layar menampilkan "Terjadi kesalahan di server. Coba lagi beberapa saat lagi."

Dua sebab bertumpuk, dan keduanya hanya terlihat bila endpointnya benar-benar
dipanggil:

  1. Penjaga "dokumen sudah lunas" memakai toleransi lima rupiah TANPA SYARAT.
     Toleransi itu ada untuk menyerap sisa pembulatan pajak — beberapa rupiah
     yang tertinggal SETELAH pembayaran. Dipakai tanpa syarat, ia menyatakan
     setiap dokumen yang nilainya sendiri di bawah lima rupiah sudah lunas,
     sehingga dokumen itu tidak pernah dapat dibayar sama sekali.

  2. Rutenya menjadikan SETIAP kegagalan sebagai 500 "Internal server error" —
     termasuk penolakan yang disengaja dan sudah membawa pesannya sendiri.
     Yang sampai ke pemakai hanya "terjadi kesalahan di server, coba lagi
     nanti", sehingga ia mencoba lagi; padahal mencoba lagi tidak akan pernah
     berhasil, dan yang perlu diperbaiki adalah angkanya.

Yang kedua inilah yang membuat yang pertama sulit ditemukan: sebabnya sudah
dihitung dengan benar dan sudah punya kalimatnya sendiri, lalu dibuang tepat
sebelum sampai ke layar.

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


async def _buat_beban(klien, bersihkan, dpp: float, pph: float = 0) -> int:
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
            "pphPercentage": pph,
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


async def _bayar(klien, bersihkan, beban_id: int, nominal: float):
    from models.payment_outgoing_model import payments_outgoing_table

    r = await klien.post(
        "/outgoing-payments/",
        json={
            "purchaseID": None,
            "expenseID": beban_id,
            "reimbursementID": None,
            "salarySlipID": None,
            "date": str(d.today()),
            "amount": nominal,
            "bankAccountID": None,
            "status": "ready",
        },
    )
    if r.status_code == 200:
        payment_id = r.json().get("payment_id") or r.json().get("id")
        if payment_id:
            bersihkan(payments_outgoing_table, payment_id)
    return r


# ----------------------------------------------------------------------
# Kejadian yang dilaporkan
# ----------------------------------------------------------------------

async def test_slip_beban_bernilai_kecil_berhasil_dibuat(klien, bersihkan):
    """
    Inti laporannya: beban Rp 0,11, slipnya ditolak.

    Nilainya memang tidak wajar — ia percobaan. Tetapi yang menolaknya bukan
    pemeriksaan kewajaran melainkan penjaga "sudah lunas", dan penjaga itu
    salah menyimpulkan: belum sepeser pun dibayar.
    """
    beban_id = await _buat_beban(klien, bersihkan, 0.11)

    r = await _bayar(klien, bersihkan, beban_id, 0.11)
    assert r.status_code == 200, r.text


async def test_beban_kecil_tetap_ditolak_pada_pembayaran_kedua(klien, bersihkan):
    """
    Perbaikannya tidak boleh melumpuhkan penjaganya.

    Setelah dibayar penuh, pembayaran berikutnya tetap harus ditolak — dan
    ditolak sebagai PERMINTAAN yang keliru (4xx), bukan sebagai kerusakan
    server.
    """
    beban_id = await _buat_beban(klien, bersihkan, 0.11)
    assert (await _bayar(klien, bersihkan, beban_id, 0.11)).status_code == 200

    r = await _bayar(klien, bersihkan, beban_id, 0.11)
    assert 400 <= r.status_code < 500, r.text


# ----------------------------------------------------------------------
# Penolakan yang disengaja tidak boleh menyamar sebagai galat server
# ----------------------------------------------------------------------

async def test_slip_kedua_ditolak_dengan_4xx_bukan_500(klien, bersihkan):
    """
    500 berarti "sistemnya bermasalah, coba lagi nanti" — dan pemakai
    memang mencoba lagi. Padahal mencoba lagi tidak akan pernah berhasil.
    """
    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)
    assert (await _bayar(klien, bersihkan, beban_id, 1_000_000)).status_code == 200

    r = await _bayar(klien, bersihkan, beban_id, 1_000_000)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "PAYMENT_LOCKED"


async def test_slip_tertunda_tidak_disebut_lunas(klien, bersihkan):
    """
    Slip yang menunggu persetujuan bukan dokumen lunas.

    Keduanya sama-sama menolak slip baru, tetapi yang perlu dilakukan
    pemakai berbeda sama sekali: yang satu sudah selesai, yang satu lagi
    justru menunggu tindakan seseorang. Kalimat yang keliru mengirimnya
    mencari dokumen itu di daftar yang salah.
    """
    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)
    assert (await _bayar(klien, bersihkan, beban_id, 1_000_000)).status_code == 200

    r = await _bayar(klien, bersihkan, beban_id, 1_000_000)
    pesan = r.json()["detail"]["message"].lower()
    assert "menunggu persetujuan" in pesan
    assert "lunas" not in pesan


async def test_slip_tertunda_memesan_nominalnya(klien, bersihkan):
    """
    Jalur duplikat yang paling sering terjadi: tombol simpan tertekan dua
    kali, dua slip terbentuk, keduanya disetujui belakangan oleh orang yang
    tidak tahu ada dua — dan uangnya keluar dua kali.

    Slip yang belum disetujui karena itu ikut memesan nominalnya. Pemesanan
    itu tidak permanen: menolak slip mengembalikannya.
    """
    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)
    assert (await _bayar(klien, bersihkan, beban_id, 600_000)).status_code == 200

    # Sisa tinggal 400.000, walaupun belum satu pun disetujui.
    assert (await _bayar(klien, bersihkan, beban_id, 600_000)).status_code == 400
    assert (await _bayar(klien, bersihkan, beban_id, 400_000)).status_code == 200


async def test_nominal_melebihi_sisa_ditolak_dengan_alasannya(klien, bersihkan):
    """
    Pesannya harus menyebut BERAPA yang masih boleh dibayarkan. Tanpa itu,
    yang mengisi hanya tahu angkanya ditolak, bukan angka mana yang benar.
    """
    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)

    r = await _bayar(klien, bersihkan, beban_id, 5_000_000)
    assert r.status_code == 400, r.text
    assert "sisa" in r.text.lower()


async def test_pembayaran_pertama_penuh_tetap_diterima(klien, bersihkan):
    """
    Penjaganya menolak yang MELEBIHI, bukan yang tepat. Toleransi lima rupiah
    juga tidak boleh menolak pembayaran yang meleset karena pembulatan pajak.
    """
    beban_id = await _buat_beban(klien, bersihkan, 1_000_000, pph=2)
    nilai = 1_000_000 - (1_000_000 * 2 / 100)

    assert (await _bayar(klien, bersihkan, beban_id, nilai)).status_code == 200
    assert (await _bayar(klien, bersihkan, beban_id, nilai - 3)).status_code == 400


async def test_pembayaran_sebagian_masih_menyisakan_tagihan(klien, bersihkan):
    """
    Sisa yang masih besar tidak boleh ikut tersapu toleransi.
    """
    beban_id = await _buat_beban(klien, bersihkan, 1_000_000)
    assert (await _bayar(klien, bersihkan, beban_id, 400_000)).status_code == 200

    r = await _bayar(klien, bersihkan, beban_id, 600_000)
    assert r.status_code == 200, r.text
