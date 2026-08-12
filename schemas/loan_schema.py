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

    Nilai pinjaman (`received`) dan sisa utang (`debt`) sengaja tidak ada di
    sini: keduanya sudah menjadi dasar pencatatan pembayaran masuk dan keluar,
    sehingga mengubahnya membuat angkanya tidak lagi cocok dengan riwayat
    transaksi — dan selisihnya tidak akan terlihat di mana pun.

    Yang paling sering perlu diperbaiki justru data rekening, dan itu ada di
    sini.
    """

    creditorName: Optional[str] = None
    creditorAddress: Optional[str] = None
    creditorNPWP: Optional[str] = None
    description: Optional[str] = None
    bankAccountName: Optional[str] = None
    bankAccountNumber: Optional[str] = None
    bankName: Optional[str] = None
    bankAccountID: Optional[int] = None


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