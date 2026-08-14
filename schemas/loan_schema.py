from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime

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
    pass


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