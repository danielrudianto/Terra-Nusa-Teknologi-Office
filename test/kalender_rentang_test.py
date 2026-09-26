"""
Unduh kalender per RENTANG TANGGAL.

Tiga hal yang dijaga di sini, dan tidak satu pun menghasilkan galat bila
salah:

  * **Batasnya ditegakkan di server.** Dialognya membatasi pilihan menjadi
    60 hari, tetapi dialog bukan pengaman: `?start=2020-01-01&end=2026-12-31`
    tidak menyentuhnya sama sekali. Berkasnya dirakit di PERAMBAN — seluruh
    transaksi rentang itu dikirim utuh — jadi rentang setahun membuat tab-nya
    diam bermenit-menit tanpa satu pun pesan, dan yang menunggunya menutupnya
    lebih dulu.

  * **Saldo awalnya diambil sebelum `mulai`, bukan sebelum tanggal 1 bulan.**
    Ini yang paling berbahaya: rentang yang mulai tanggal 15 dengan saldo awal
    tanggal 1 menggeser SELURUH garis saldonya sebanyak mutasi dua pekan
    pertama. Garis yang bergeser rata tetap terlihat masuk akal, dan tidak ada
    satu angka pun yang tampak ganjil.

  * **Batas atasnya eksklusif, dan hari terakhir tetap ikut.** `akhir` yang
    diteruskan apa adanya sebagai batas `<` membuang hari terakhir rentangnya
    — satu hari, di ujung, tempat orang paling tidak mencarinya.
"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from controllers.calendar_controller import CalendarController


def _tanpa_db():
    """Menambal keempat sumber data; yang diperiksa argumennya, bukan isinya."""
    return (
        patch(
            "controllers.calendar_controller.BankAccount.get_bank_accounts_by_ids",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "controllers.calendar_controller.PaymentOutgoingRepository.download_calendar_rentang",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "controllers.calendar_controller.InterpaymentRepository.get_calendar_rentang",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "controllers.calendar_controller.PaymentIncomingRepository.get_calendar_rentang",
            new=AsyncMock(return_value=[]),
        ),
        # `Mutation` di sini tiruan dari conftest — kelas kosong, karena modul
        # aslinya memuat view `mutation` lewat `autoload_with` dan tidak dapat
        # diimpor tanpa basis data. Karena itu `create=True`.
        #
        # `create=True` biasanya BERBAHAYA: ia membuat tambalan atas nama yang
        # salah tetap lolos, sehingga uji ini tetap hijau meski metodenya
        # dinamai lain di kode sungguhan. Penangkalnya
        # `test_metode_saldo_rentang_benar_benar_ada` di bawah, yang membaca
        # berkas aslinya.
        patch(
            "controllers.calendar_controller.Mutation.download_calendar_rentang",
            new=AsyncMock(return_value=[]),
            create=True,
        ),
    )


# ----------------------------------------------------------------------
# Batas rentang
# ----------------------------------------------------------------------


async def test_rentang_lebih_dari_batas_ditolak_di_server():
    """
    Bukan dialognya yang menentukan.

    Kalau penolakan ini hilang, tidak ada yang rusak di layar — permintaannya
    diterima, lalu perambannya menggantung. Kegagalan yang tampak seperti
    jaringan lambat, bukan seperti bug.
    """
    n = CalendarController.MAKS_HARI_RENTANG
    mulai = date(2026, 1, 1)
    hasil = await CalendarController.download_calendar_rentang(
        mulai, mulai.replace(day=1) + __import__("datetime").timedelta(days=n), None
    )
    assert hasil["status"] == 400
    assert str(n) in hasil["error"], "pesannya harus menyebut batasnya, bukan sekadar menolak"


async def test_rentang_tepat_sebesar_batas_diterima():
    """
    Batasnya inklusif. Salah satu ujung yang meleset satu hari membuat
    pilihan terakhir di dialognya ditolak server — dan yang memakainya akan
    mengira dialognya yang rusak.
    """
    from datetime import timedelta

    n = CalendarController.MAKS_HARI_RENTANG
    mulai = date(2026, 1, 1)
    akhir = mulai + timedelta(days=n - 1)

    tambalan = _tanpa_db()
    for t in tambalan:
        t.start()
    try:
        hasil = await CalendarController.download_calendar_rentang(mulai, akhir, None)
    finally:
        for t in tambalan:
            t.stop()

    assert "error" not in hasil
    assert hasil["start"] == "2026-01-01"
    assert hasil["end"] == akhir.isoformat()


async def test_akhir_mendahului_mulai_ditolak():
    hasil = await CalendarController.download_calendar_rentang(
        date(2026, 3, 10), date(2026, 3, 1), None
    )
    assert hasil["status"] == 400


# ----------------------------------------------------------------------
# Saldo awal
# ----------------------------------------------------------------------


def test_metode_saldo_rentang_benar_benar_ada():
    """
    Penangkal `create=True` di atas.

    Modul `models/mutation_model.py` tidak dapat diimpor tanpa basis data —
    ia memuat view `mutation` lewat `autoload_with` — sehingga tambalannya
    terpaksa dibuat atas kelas tiruan. Tanpa pemeriksaan ini, metodenya
    boleh dinamai apa saja di kode sungguhan dan seluruh uji di berkas ini
    tetap hijau.

    Yang dibaca berkas sumbernya, bukan modulnya.
    """
    import ast
    from pathlib import Path

    sumber = Path(__file__).resolve().parents[1] / "models" / "mutation_model.py"
    pohon = ast.parse(sumber.read_text(encoding="utf-8"))

    metode = {
        n.name
        for kelas in pohon.body
        if isinstance(kelas, ast.ClassDef) and kelas.name == "Mutation"
        for n in kelas.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "download_calendar_rentang" in metode, (
        "Mutation.download_calendar_rentang tidak ada; tambalan `create=True` "
        "di berkas ini membuat seluruh ujinya tetap hijau tanpa metode itu."
    )
    assert "_saldo_awal_sebelum" in metode, (
        "kueri saldo awal harus punya bentuk yang menerima TANGGAL; tanpa itu "
        "rentang hanya dapat bertitik nol di tanggal 1 bulan."
    )


async def test_saldo_awal_diambil_sebelum_mulai_bukan_awal_bulan():
    """
    Rentang 15–30 September memakai saldo per 15 September.

    Memakai saldo awal BULAN menggeser seluruh garisnya sebanyak mutasi
    tanggal 1–14 — dan tidak ada satu baris pun yang terlihat salah.
    """
    tambalan = _tanpa_db()
    for t in tambalan:
        t.start()
    try:
        from controllers.calendar_controller import Mutation

        await CalendarController.download_calendar_rentang(
            date(2026, 9, 15), date(2026, 9, 30), [7]
        )
        Mutation.download_calendar_rentang.assert_awaited_once()
        args = Mutation.download_calendar_rentang.await_args.args
        assert args[0] == date(2026, 9, 15), (
            "titik nol saldo harus hari pertama RENTANG, bukan tanggal 1 bulan"
        )
    finally:
        for t in tambalan:
            t.stop()


# ----------------------------------------------------------------------
# Batas atas eksklusif
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "nama",
    [
        "PaymentOutgoingRepository.download_calendar_rentang",
        "InterpaymentRepository.get_calendar_rentang",
        "PaymentIncomingRepository.get_calendar_rentang",
    ],
)
async def test_hari_terakhir_ikut_terbawa(nama):
    """
    Batas atas yang diteruskan ke repository adalah `akhir + 1 hari`.

    Kalau `akhir` diteruskan apa adanya, transaksi hari terakhir hilang —
    seluruhnya, diam-diam, dan hanya pada hari yang paling jarang diperiksa.
    """
    from datetime import timedelta

    tambalan = _tanpa_db()
    for t in tambalan:
        t.start()
    try:
        import controllers.calendar_controller as modul

        await CalendarController.download_calendar_rentang(
            date(2026, 9, 1), date(2026, 9, 30), None
        )

        obj = modul
        for bagian in nama.split("."):
            obj = getattr(obj, bagian)

        obj.assert_awaited_once()
        mulai_arg, akhir_arg = obj.await_args.args[0], obj.await_args.args[1]
        assert mulai_arg == date(2026, 9, 1)
        assert akhir_arg == date(2026, 9, 30) + timedelta(days=1), (
            f"{nama} menerima batas atas {akhir_arg}; hari terakhir rentangnya "
            f"tidak akan ikut terbawa"
        )
    finally:
        for t in tambalan:
            t.stop()


# ----------------------------------------------------------------------
# Rentang lintas bulan
# ----------------------------------------------------------------------


async def test_rentang_boleh_melintasi_bulan_dan_tahun():
    """
    Justru inilah yang diminta: dua bulan sekaligus.

    Penyaring lama memakai `EXTRACT(month)` dan `EXTRACT(year)` — bentuk yang
    secara harfiah tidak dapat menyatakan rentang lintas bulan. Kalau
    seseorang mengembalikannya, rentang 20 Des–10 Jan akan mengembalikan
    kosong, bukan galat.
    """
    tambalan = _tanpa_db()
    for t in tambalan:
        t.start()
    try:
        import controllers.calendar_controller as modul

        hasil = await CalendarController.download_calendar_rentang(
            date(2026, 12, 20), date(2027, 1, 10), None
        )
        assert "error" not in hasil
        args = modul.PaymentOutgoingRepository.download_calendar_rentang.await_args.args
        assert args[0] == date(2026, 12, 20)
        assert args[1] == date(2027, 1, 11)
    finally:
        for t in tambalan:
            t.stop()
