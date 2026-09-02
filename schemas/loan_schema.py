from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import date, datetime

# Selisih rupiah yang masih dianggap sama saat nilai uang dibandingkan.
#
# Angka yang sama dengan penjaga `LOAN_BELOW_PAID` di controller, dan dengan
# ambang lunas di repository. Nilai disimpan sebagai desimal sementara yang
# dikirim layar berupa pecahan, sehingga selisih beberapa rupiah adalah
# pembulatan, bukan kekeliruan yang perlu ditolak.
TOLERANSI_RUPIAH = 5

class LoanBase(BaseModel):
    date: date
    creditorName: str
    creditorAddress: str
    creditorNPWP: Optional[str] = None
    description: str
    received: float = Field(ge=0)
    debt: float = Field(ge=0)
    bankAccountName: str
    bankAccountNumber: str
    bankName: str
    # rekening perusahaan tujuan penerimaan dana (dari bank_accounts)
    bankAccountID: Optional[int] = None

class LoanCreate(LoanBase):
    """
    Pinjaman baru.

    Penjaga `received <= debt` ditaruh DI SINI, bukan di `LoanBase`. `LoanBase`
    juga menurunkan `LoanResponse`, yang dipakai membaca baris yang sudah
    tersimpan — dan aturan yang ikut berlaku saat MEMBACA berarti satu baris
    lama yang melanggar tidak lagi bisa ditampilkan sama sekali. Penjaga yang
    menolak menampilkan data yang sudah terlanjur ada jauh lebih merepotkan
    daripada data yang salah itu sendiri.
    """

    @model_validator(mode="after")
    def _diterima_tidak_melebihi_utang(self):
        """
        Dana yang diterima tidak mungkin melebihi utangnya.

        `received` adalah pokok yang benar-benar masuk ke rekening; `debt`
        adalah yang harus dikembalikan — pokok DITAMBAH bunga dan biaya. Maka
        `debt >= received` selalu, dan sama persis pun sah (pinjaman tanpa
        bunga dari keluarga atau pemegang saham).

        Kebalikannya bukan sekadar janggal: ia diam-diam mencatat penerimaan
        uang yang tidak berutang kepada siapa pun, dan angkanya masuk ke saldo
        bank lewat `payment_incoming`.
        """
        if self.received > self.debt + TOLERANSI_RUPIAH:
            raise ValueError(
                "Dana diterima tidak boleh melebihi nilai utang."
            )
        return self


class LoanUpdate(BaseModel):
    """
    Kolom yang boleh disunting setelah pinjaman tercatat.

    Nilai pinjaman (`received`) dan utang (`debt`) DAPAT diubah, tetapi tidak
    bebas: `debt` tidak boleh turun di bawah jumlah yang sudah dibayarkan.
    Penjaganya ada di controller, karena ia perlu membaca riwayat pembayaran
    yang tidak tersedia di lapisan skema.

    Setiap perubahan nilai diikuti perhitungan ulang status lunas — menurunkan
    utang hingga sama dengan yang sudah dibayar menjadikannya lunas, dan
    menaikkannya kembali membatalkan status itu.
    """

    creditorName: Optional[str] = None
    creditorAddress: Optional[str] = None
    creditorNPWP: Optional[str] = None
    description: Optional[str] = None
    bankAccountName: Optional[str] = None
    bankAccountNumber: Optional[str] = None
    bankName: Optional[str] = None
    bankAccountID: Optional[int] = None
    # Nilai: tidak boleh negatif. Batas bawah yang sesungguhnya — jumlah yang
    # sudah dibayarkan — diperiksa di controller.
    received: Optional[float] = Field(default=None, ge=0)
    debt: Optional[float] = Field(default=None, ge=0)


class UpdateLoanResponse(BaseModel):
    loan_id: int

class LoanResponse(LoanBase):
    id: int
    isPaid: bool = False
    createdBy: Optional[int] = None
    createdAt: Optional[datetime] = None
    updatedBy: Optional[int] = None
    updatedAt: Optional[datetime] = None

class LoanListResponse(BaseModel):
    data: list
    count: int

class CreateLoanResponse(BaseModel):
    message: str
    loan_id: int

class LoanPaymentsResponse(BaseModel):
    loan: dict
    payments: list

class ErrorResponse(BaseModel):
    error: str
    status: int