"""
Pinjaman dan PENERIMAAN dananya bergerak bersama.

Mencatat pinjaman membuat DUA baris: pinjamannya sendiri, dan satu
`payment_incoming` yang mewakili uang masuk ke rekening perusahaan. Baris
kedua itulah yang terbaca di mutasi bank dan membentuk saldo — `loans.received`
tidak dibaca di sana sama sekali.

Sebelum perbaikan ini, pembaruan hanya menyentuh baris pertama: nilai
pinjaman berubah, penerimaannya tidak, dan saldo bank tetap memakai angka
pertama yang pernah dicatat. Tidak ada galat dan tidak ada selisih yang muncul
di mana pun, sebab kedua angka itu memang tidak pernah dibandingkan.

Diuji dengan menjalankan `update_loan` YANG SEBENARNYA di atas repository
tiruan, bukan dengan membaca ulang kodenya: yang perlu dijaga adalah bahwa
tulisan keduanya benar-benar terjadi, dan pemeriksaan teks akan tetap lulus
ketika pemanggilannya dipindah ke cabang yang tidak pernah dijalankan.
"""

import os
from datetime import date

import pytest
from fastapi import HTTPException

from controllers.loan_controller import LoanController
from schemas.loan_schema import TOLERANSI_RUPIAH

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTROLLER = os.path.join(AKAR, "controllers", "loan_controller.py")


class RepoPinjamanTiruan:
    """Repository pinjaman tiruan; menyimpan barisnya di memori."""

    def __init__(self, baris):
        self.baris = dict(baris)
        self.dibayar = 0.0
        self.update_terakhir = None

    async def get_loan_by_id(self, loan_id):
        return dict(self.baris)

    async def total_dibayar(self, loan_id):
        return self.dibayar

    async def update(self, loan_id, data, user_id):
        self.update_terakhir = dict(data)
        self.baris.update(
            {k: v for k, v in data.items() if k in self.baris or True}
        )
        return {"loan_id": loan_id}

    async def hitung_ulang_lunas(self, loan_id, user_id):
        return {"isPaid": False, "berubah": False}


class RepoPenerimaanTiruan:
    """Repository payment_incoming tiruan."""

    def __init__(self, baris=None):
        self.baris = list(baris or [])
        self.dibuat = []
        self.diubah = []
        self.gagal = False

    async def get_by_loan_id(self, loan_id):
        if self.gagal:
            return {"error": "Internal server error.", "status": 500}
        return [dict(b) for b in self.baris]

    async def create(self, data):
        if self.gagal:
            return {"error": "Internal server error.", "status": 500}
        self.dibuat.append(dict(data))
        return {"payment_id": 99}

    async def update(self, payment_id, data):
        if self.gagal:
            return {"error": "Internal server error.", "status": 500}
        self.diubah.append((payment_id, dict(data)))
        return {"affected_rows": 1}


PINJAMAN = {
    "id": 7,
    "date": date(2026, 3, 1),
    "received": 100_000_000.0,
    "debt": 120_000_000.0,
    "bankAccountID": 2,
}


@pytest.fixture
def repo(monkeypatch):
    """Pasang kedua repository tiruan ke controller."""
    pinjaman = RepoPinjamanTiruan(PINJAMAN)
    penerimaan = RepoPenerimaanTiruan(
        [{"id": 55, "loanID": 7, "amount": 100_000_000.0, "bankAccountID": 2}]
    )
    monkeypatch.setattr(
        "controllers.loan_controller.LoanRepository", pinjaman
    )
    monkeypatch.setattr(
        "controllers.loan_controller.PaymentIncomingRepository", penerimaan
    )
    return pinjaman, penerimaan


# --------------------------------------------------------------------------
# Penyelarasan penerimaan
# --------------------------------------------------------------------------


async def test_mengubah_received_ikut_mengubah_penerimaan(repo):
    """
    Inti perbaikannya.

    Sebelum ini, baris `payment_incoming` tidak pernah disentuh saat
    pembaruan — pinjaman berubah, saldo bank tidak.
    """
    pinjaman, penerimaan = repo
    await LoanController.update_loan(7, {"received": 90_000_000.0}, 1)

    assert penerimaan.diubah, "payment_incoming tidak ikut diubah"
    payment_id, data = penerimaan.diubah[0]
    assert payment_id == 55
    assert data["amount"] == 90_000_000.0


async def test_pindah_rekening_ikut_terbawa(repo):
    """
    `bankAccountID` juga disunting.

    Bila penerimaannya tertinggal di rekening lama, uangnya muncul di
    rekening yang salah — dan kedua saldo itu keliru sekaligus.
    """
    pinjaman, penerimaan = repo
    await LoanController.update_loan(7, {"bankAccountID": 9}, 1)

    assert penerimaan.diubah, "penerimaan tidak ikut pindah rekening"
    _, data = penerimaan.diubah[0]
    assert data["bankAccountID"] == 9


async def test_tanggal_penerimaan_tidak_ditimpa(repo):
    """
    `date` sengaja tidak ikut.

    Tanggal pinjaman tidak dapat disunting, dan bila seseorang membetulkan
    tanggal penerimaannya agar cocok dengan rekening koran, menimpanya akan
    membatalkan koreksi yang disengaja.
    """
    pinjaman, penerimaan = repo
    await LoanController.update_loan(7, {"received": 90_000_000.0}, 1)

    _, data = penerimaan.diubah[0]
    assert "date" not in data


async def test_mengubah_kreditur_saja_tidak_menyentuh_penerimaan(repo):
    """Perubahan yang tidak menyangkut uang tidak menulis apa pun ke sana."""
    pinjaman, penerimaan = repo
    await LoanController.update_loan(7, {"creditorName": "PT Baru"}, 1)

    assert not penerimaan.diubah
    assert not penerimaan.dibuat


async def test_pinjaman_lama_tanpa_penerimaan_dibuatkan(monkeypatch):
    """
    Pinjaman dari sebelum pencatatan otomatis ada belum punya barisnya.

    Tanpa ini, uangnya tidak pernah muncul di mutasi sama sekali — dan
    memperbaikinya lewat layar menjadi mustahil.
    """
    pinjaman = RepoPinjamanTiruan(PINJAMAN)
    penerimaan = RepoPenerimaanTiruan([])
    monkeypatch.setattr("controllers.loan_controller.LoanRepository", pinjaman)
    monkeypatch.setattr(
        "controllers.loan_controller.PaymentIncomingRepository", penerimaan
    )

    await LoanController.update_loan(7, {"received": 80_000_000.0}, 1)

    assert penerimaan.dibuat, "penerimaan yang hilang tidak dibuatkan"
    baru = penerimaan.dibuat[0]
    assert baru["loanID"] == 7
    assert baru["amount"] == 80_000_000.0
    assert baru["isApprove"] is True, "pencatatan otomatis selalu langsung sah"


async def test_penerimaan_ganda_ditolak_bukan_ditebak(monkeypatch):
    """
    Dua penerimaan berarti seseorang menambahkannya sendiri — mungkin
    pencairan bertahap.

    Memilih salah satu berarti mengubah angka yang bukan haknya; membagi rata
    berarti mengarang. Ditolak dengan sebutan yang jelas.
    """
    pinjaman = RepoPinjamanTiruan(PINJAMAN)
    penerimaan = RepoPenerimaanTiruan(
        [
            {"id": 55, "loanID": 7, "amount": 60_000_000.0, "bankAccountID": 2},
            {"id": 56, "loanID": 7, "amount": 40_000_000.0, "bankAccountID": 2},
        ]
    )
    monkeypatch.setattr("controllers.loan_controller.LoanRepository", pinjaman)
    monkeypatch.setattr(
        "controllers.loan_controller.PaymentIncomingRepository", penerimaan
    )

    with pytest.raises(HTTPException) as galat:
        await LoanController.update_loan(7, {"received": 90_000_000.0}, 1)

    assert galat.value.status_code == 409
    assert galat.value.detail["code"] == "LOAN_RECEIPT_AMBIGUOUS"
    assert not penerimaan.diubah, "tidak boleh menebak salah satu"


async def test_kegagalan_penyelarasan_tidak_ditelan(monkeypatch):
    """
    Jawaban berhasil atas penyelarasan yang gagal mengulang persis cacat yang
    sedang diperbaiki — hanya lebih sulit ditemukan.
    """
    pinjaman = RepoPinjamanTiruan(PINJAMAN)
    penerimaan = RepoPenerimaanTiruan(
        [{"id": 55, "loanID": 7, "amount": 100_000_000.0, "bankAccountID": 2}]
    )
    penerimaan.gagal = True
    monkeypatch.setattr("controllers.loan_controller.LoanRepository", pinjaman)
    monkeypatch.setattr(
        "controllers.loan_controller.PaymentIncomingRepository", penerimaan
    )

    with pytest.raises(HTTPException) as galat:
        await LoanController.update_loan(7, {"received": 90_000_000.0}, 1)

    assert galat.value.status_code == 500
    assert galat.value.detail["code"] == "LOAN_RECEIPT_SYNC_FAILED"


# --------------------------------------------------------------------------
# Dana diterima tidak melebihi utang
# --------------------------------------------------------------------------


async def test_received_melebihi_debt_ditolak(repo):
    """
    `debt` adalah pokok DITAMBAH bunga dan biaya, jadi ia selalu >= `received`.

    Kebalikannya mencatat penerimaan uang yang tidak berutang kepada siapa
    pun — dan angkanya masuk ke saldo bank lewat `payment_incoming`.
    """
    pinjaman, penerimaan = repo
    with pytest.raises(HTTPException) as galat:
        await LoanController.update_loan(7, {"received": 130_000_000.0}, 1)

    assert galat.value.status_code == 409
    assert galat.value.detail["code"] == "LOAN_RECEIVED_ABOVE_DEBT"
    assert not penerimaan.diubah


async def test_dibandingkan_dengan_nilai_tersimpan_bukan_muatan(repo):
    """
    Pembaruan boleh SEBAGIAN.

    Layar yang hanya mengubah `received` tidak mengirim `debt` sama sekali.
    Bila pemeriksaannya hanya berjalan ketika keduanya ada pada muatan,
    aturannya lolos justru pada perubahan yang paling mungkin melanggarnya —
    dan itulah bentuk permintaan yang dikirim layar pinjaman.
    """
    pinjaman, penerimaan = repo
    # `debt` tersimpan 120 juta; muatan hanya membawa `received`. Selisihnya
    # dibuat jauh di atas toleransi pembulatan agar yang diuji benar-benar
    # aturannya, bukan ambangnya.
    with pytest.raises(HTTPException) as galat:
        await LoanController.update_loan(7, {"received": 121_000_000.0}, 1)
    assert galat.value.detail["code"] == "LOAN_RECEIVED_ABOVE_DEBT"


async def test_menurunkan_debt_di_bawah_received_juga_ditolak(repo):
    """Arah sebaliknya sama saja — yang dijaga hubungannya, bukan kolomnya."""
    pinjaman, penerimaan = repo
    with pytest.raises(HTTPException) as galat:
        await LoanController.update_loan(7, {"debt": 50_000_000.0}, 1)
    assert galat.value.detail["code"] == "LOAN_RECEIVED_ABOVE_DEBT"


async def test_sama_persis_tetap_boleh(repo):
    """Pinjaman tanpa bunga — dari keluarga atau pemegang saham — sah."""
    pinjaman, penerimaan = repo
    await LoanController.update_loan(7, {"received": 120_000_000.0}, 1)
    assert penerimaan.diubah


async def test_selisih_pembulatan_tidak_ditolak(repo):
    """
    Toleransi yang sama dengan penjaga `LOAN_BELOW_PAID` dan ambang lunas.

    Nilai disimpan sebagai desimal sementara layar mengirim pecahan; selisih
    beberapa rupiah adalah pembulatan, bukan kekeliruan.
    """
    pinjaman, penerimaan = repo
    await LoanController.update_loan(
        7, {"received": 120_000_000.0 + TOLERANSI_RUPIAH}, 1
    )
    assert penerimaan.diubah


async def test_penjaga_utang_di_bawah_terbayar_masih_berlaku(repo):
    """Penjaga lama tidak boleh hilang karena penjaga baru ditambahkan."""
    pinjaman, penerimaan = repo
    pinjaman.dibayar = 90_000_000.0

    with pytest.raises(HTTPException) as galat:
        await LoanController.update_loan(7, {"debt": 50_000_000.0}, 1)
    assert galat.value.detail["code"] == "LOAN_BELOW_PAID"


# --------------------------------------------------------------------------
# Bentuk yang harus tetap sama antara mencatat dan memperbarui
# --------------------------------------------------------------------------


def test_create_dan_update_menulis_kolom_yang_sama():
    """
    Baris penerimaan yang lahir saat pembaruan harus sama bentuknya dengan
    yang lahir saat pencatatan.

    Bila keduanya berbeda, satu pinjaman akan berperilaku lain dari pinjaman
    di sebelahnya tergantung kapan barisnya dibuat — dan itu jenis selisih
    yang tidak akan pernah dicurigai orang.
    """
    s = open(CONTROLLER, encoding="utf-8").read()
    for kolom in ('"loanID"', '"bankAccountID"', '"isApprove"', '"amount"'):
        assert s.count(kolom) >= 2, f"{kolom} tidak muncul di kedua jalur"
