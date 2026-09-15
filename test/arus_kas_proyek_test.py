"""
Arus kas proyek: SQL-nya diperiksa, bukan sekadar hasil tiruannya.

KENAPA DIUJI LEWAT SQL YANG DIHASILKAN

Kekeliruan yang paling mungkin di modul ini tidak menghasilkan galat apa pun.
Ia menghasilkan ANGKA LAIN:

  * `payment_incoming.salesInvoiceID` dideklarasikan `ForeignKey("purchases.id")`
    di modelnya — menunjuk tabel yang SALAH, sehingga SQLAlchemy tidak mengenal
    satu pun hubungan antara `payment_incoming` dan `sales_invoices`.
    Menyederhanakan join-nya menjadi `.join(sales_invoice_tables)` karena itu
    gagal dengan `NoForeignKeysError` — dan repository MENELAN galat itu
    menjadi `internal_error()`, sehingga yang sampai ke layar hanyalah 500
    tanpa sebab. Uji di bawah menyebut sebabnya.

  * Menambahkan `isApprove == True` terasa seperti pengetatan yang benar,
    padahal membuat halaman ini melaporkan kas yang berbeda dari kalender untuk
    uang yang sama.

  * Lupa menyaring `isDelete` pada DOKUMEN INDUKNYA membuat penghapusan sebuah
    pembelian justru MENAIKKAN kas keluar proyeknya.

Uji yang memeriksa nilai kembalian tiruan tidak akan menangkap satu pun dari
ketiganya. Yang ditangkap di sini adalah kuerinya sendiri.
"""

import os
import re

import pytest

from controllers.project_cashflow_controller import ProjectCashflowController
from repository import project_cashflow_repository as modul
from repository.project_cashflow_repository import ProjectCashflowRepository

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Tangkap:
    """Menggantikan `database`; merekam kueri lalu mengembalikan kosong."""

    def __init__(self):
        self.sql = []

    async def fetch_all(self, kueri):
        # Tanda kutip SQLAlchemy dibuang.
        #
        # Kolom berhuruf besar dikutip (`purchases."isDelete"`), yang lain
        # tidak. Uji yang mencocokkan apa adanya akan gagal atau lolos
        # tergantung kapitalisasi nama kolom — yang tidak ada hubungannya
        # dengan hal yang sedang dijaga.
        self.sql.append(" ".join(str(kueri).split()).replace('"', ""))
        return []


@pytest.fixture
def tangkap(monkeypatch):
    t = _Tangkap()
    monkeypatch.setattr(modul, "database", t)
    return t


# ----------------------------------------------------------------------
# Sambungan tabel
# ----------------------------------------------------------------------


async def test_kas_masuk_menyambung_ke_faktur_bukan_pembelian(tangkap):
    """
    FK pada modelnya menunjuk `purchases.id`; sambungannya harus ditulis sendiri.

    Tanpa `onclause`, SQLAlchemy tidak menemukan hubungan apa pun ke
    `sales_invoices` dan melempar — lalu repository menelannya menjadi 500.
    Yang dijaga di sini karena itu bukan cuma "jangan menyentuh purchases",
    melainkan bahwa sambungannya memang disebut kolom demi kolom.
    """
    await ProjectCashflowRepository.kas_masuk("R501")

    assert len(tangkap.sql) == 1
    sql = tangkap.sql[0]
    assert "sales_invoices" in sql, "tidak menyambung ke faktur penjualan"
    assert (
        "payment_incoming.salesInvoiceID = sales_invoices.id" in sql
    ), f"sambungannya bukan ke faktur: {sql}"
    assert "purchases" not in sql, (
        "kueri kas masuk menyentuh `purchases` — FK yang salah itu diikuti"
    )


async def test_kas_keluar_punya_dua_sumber_yang_tersambung_sendiri(tangkap):
    await ProjectCashflowRepository.kas_keluar("R501")

    assert len(tangkap.sql) == 2, "kas keluar harus dari pembelian DAN reimbursement"
    gabung = " || ".join(tangkap.sql)
    assert "payment_outgoing.purchaseID = purchases.id" in gabung
    assert (
        "payment_outgoing.reimbursementID = reimbursements.id" in gabung
    ), "reimbursement tidak tersambung lewat kolomnya sendiri"


# ----------------------------------------------------------------------
# Saringan
# ----------------------------------------------------------------------


async def test_dokumen_induk_yang_terhapus_ikut_disaring(tangkap):
    """
    Tanpa ini, MENGHAPUS sebuah pembelian justru menaikkan kas keluar proyek.

    Arah yang berlawanan dengan dugaan siapa pun, dan tanpa satu pun galat.
    """
    await ProjectCashflowRepository.kas_keluar("R501")
    await ProjectCashflowRepository.kas_masuk("R501")

    pasangan = [
        ("purchases", "payment_outgoing"),
        ("reimbursements", "payment_outgoing"),
        ("sales_invoices", "payment_incoming"),
    ]
    for sql in tangkap.sql:
        for induk, bayar in pasangan:
            if f"{induk}.projectName" not in sql:
                continue
            assert f"{induk}.isDelete =" in sql, f"{induk} tidak disaring: {sql}"
            assert f"{bayar}.isDelete =" in sql, f"{bayar} tidak disaring: {sql}"


async def test_tidak_menyaring_isApprove(tangkap):
    """
    Sengaja TIDAK disaring — mengikuti kalender kas dan saldo bank.

    Penolakan dan pembatalan sudah mencabut `isApprove` SEKALIGUS menyetel
    `isDelete`, jadi `isDelete = 0` sudah berarti pembayarannya berlaku.
    Menambahkan `isApprove` di sini membuat laporan proyek melaporkan kas yang
    berbeda dari kalender untuk uang yang sama — dan yang menemukannya tidak
    punya cara tahu mana yang benar.
    """
    await ProjectCashflowRepository.kas_keluar("R501")
    await ProjectCashflowRepository.kas_masuk("R501")

    for sql in tangkap.sql:
        assert "isApprove" not in sql, (
            "menyaring `isApprove` membuat angkanya berbeda dari kalender kas"
        )


async def test_proyeknya_benar_benar_disaring(tangkap):
    await ProjectCashflowRepository.kas_keluar("R501")
    await ProjectCashflowRepository.kas_masuk("R501")

    for sql in tangkap.sql:
        assert "projectName" in sql, f"kueri tanpa saringan proyek: {sql}"


# ----------------------------------------------------------------------
# Controller
# ----------------------------------------------------------------------


async def test_sumber_kosong_bukan_galat(monkeypatch):
    """
    Proyek yang baru berjalan punya kas keluar tanpa kas masuk; yang berjalan
    dengan uang muka punya kebalikannya. Keduanya harus tergambar.
    """
    async def kosong(_):
        return []

    monkeypatch.setattr(ProjectCashflowRepository, "kas_keluar", kosong)
    monkeypatch.setattr(ProjectCashflowRepository, "kas_masuk", kosong)

    hasil = await ProjectCashflowController.arus_kas("R501")
    assert hasil["outgoing"] == []
    assert hasil["incoming"] == []
    assert "error" not in hasil


async def test_galat_sungguhan_tetap_dilemparkan(monkeypatch):
    """
    Kueri gagal TIDAK boleh jadi daftar kosong.

    Proyek tanpa arus kas dan proyek yang datanya gagal dibaca akan tampak
    persis sama di layar — dan yang membacanya menyimpulkan yang pertama.
    """
    async def meledak(_):
        return {"error": "Internal server error.", "status": 500}

    async def kosong(_):
        return []

    monkeypatch.setattr(ProjectCashflowRepository, "kas_keluar", meledak)
    monkeypatch.setattr(ProjectCashflowRepository, "kas_masuk", kosong)

    hasil = await ProjectCashflowController.arus_kas("R501")
    assert hasil.get("status") == 500


async def test_cakupan_keluar_disebut_di_jawabannya(monkeypatch):
    """
    `expenses` dan `salary_slips` tidak punya kolom proyek, jadi kas keluarnya
    batas bawah. Keterangan itu ikut di JAWABAN, bukan cuma di template —
    supaya pemakai berikutnya tidak mewarisi angkanya tanpa batasannya.
    """
    async def kosong(_):
        return []

    monkeypatch.setattr(ProjectCashflowRepository, "kas_keluar", kosong)
    monkeypatch.setattr(ProjectCashflowRepository, "kas_masuk", kosong)

    hasil = await ProjectCashflowController.arus_kas("R501")
    assert hasil["cakupanKeluar"] == ["pembelian", "reimbursement"]


async def test_nama_proyek_kosong_ditolak():
    for buruk in ("", "   ", None):
        hasil = await ProjectCashflowController.arus_kas(buruk)
        assert hasil.get("status") == 400


# ----------------------------------------------------------------------
# Izin
# ----------------------------------------------------------------------


def test_rutenya_dijaga_payment_outgoing_bukan_purchase():
    """
    `purchase:read` minimum LEVEL 1; `payment_outgoing:read` LEVEL 3.

    Laporan proyek dibuka lapangan dan pengadaan, dan justru merekalah yang
    oleh matriks izin sengaja dijauhkan dari data kas. Rute yang mengembalikan
    hal yang sama lewat pintu yang lebih rendah membatalkan keputusan itu tanpa
    mengubah satu baris pun di matriksnya.
    """
    s = open(os.path.join(AKAR, "routes/project_routes.py"), encoding="utf-8").read()
    s = "\n".join(b for b in s.splitlines() if not b.lstrip().startswith("#"))

    m = re.search(
        r'@router\.get\("/\{project_name\}/cashflow"\)(.*?)(?=@router\.)', s, re.S
    )
    assert m, "rute arus kas tidak ditemukan"
    blok = m.group(1)
    assert 'require("payment_outgoing", "read")' in blok, (
        f"penjaganya bukan payment_outgoing: {blok}"
    )
    assert '"purchase"' not in blok


def test_payment_outgoing_memang_level_tiga():
    """Penjaga di atas hanya berarti selama levelnya memang lebih tinggi."""
    from constants.permission_matrix import MATRIX

    assert MATRIX["payment_outgoing"][0] == 3
    assert MATRIX["purchase"][0] == 1
    assert MATRIX["payment_incoming"][0] == 3
