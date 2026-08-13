from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


class ProjectBase(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=1, max_length=255)
    clientID: Optional[int] = None
    description: Optional[str] = Field(default=None, max_length=500)
    startDate: Optional[date] = None
    endDate: Optional[date] = None
    isActive: Optional[bool] = True
    isCancelled: Optional[bool] = False

    @field_validator("code")
    @classmethod
    def kode_seragam(cls, v: str) -> str:
        """
        Kode disimpan huruf besar tanpa spasi tepi.

        Dokumen lama menulis kode dengan cara yang tidak seragam. Jika
        penyeragaman ini hanya dilakukan di layar, satu pemanggilan API dari
        tempat lain sudah cukup untuk memasukkan kembali kode yang tidak
        cocok — dan pencocokan dokumen ke proyek kembali meleset.
        """
        return (v or "").strip().upper()


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    # `code` boleh diubah, TETAPI hanya selama belum dipakai dokumen mana pun.
    #
    # Kode adalah satu-satunya penghubung ke dokumen yang sudah ada;
    # menggantinya setelah dipakai membuat purchase, reimbursement, dan sales
    # invoice lama tetap menunjuk kode lama. Pemeriksaannya di controller,
    # karena hanya di sana jumlah dokumennya dapat dihitung.
    code: Optional[str] = Field(default=None, min_length=2, max_length=20)
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    clientID: Optional[int] = None
    description: Optional[str] = Field(default=None, max_length=500)
    startDate: Optional[date] = None
    endDate: Optional[date] = None
    isActive: Optional[bool] = None
    isCancelled: Optional[bool] = None


class ContractBase(BaseModel):
    documentNumber: str = Field(min_length=1, max_length=100)
    documentType: Optional[str] = Field(default="spk")
    # Boleh negatif: adendum pengurangan lingkup kerja memang mengurangi
    # nilai kontrak.
    # DPP, belum termasuk PPN. Adendum pengurangan bernilai negatif.
    value: Decimal
    date: date
    description: Optional[str] = Field(default=None, max_length=500)

    @field_validator("documentType")
    @classmethod
    def jenis_dikenal(cls, v: Optional[str]) -> str:
        sah = {"spk", "adendum"}
        nilai = (v or "spk").strip().lower()
        if nilai not in sah:
            raise ValueError(f"documentType harus salah satu dari: {', '.join(sorted(sah))}")
        return nilai

    @field_validator("value")
    @classmethod
    def bukan_nol(cls, v: Decimal) -> Decimal:
        if v == 0:
            raise ValueError("nilai kontrak tidak boleh nol")
        return v


class ContractCreate(ContractBase):
    pass


class ContractUpdate(BaseModel):
    documentNumber: Optional[str] = Field(default=None, min_length=1, max_length=100)
    documentType: Optional[str] = None
    value: Optional[Decimal] = None
    date: Optional[date] = None
    description: Optional[str] = Field(default=None, max_length=500)


class ContractResponse(ContractBase):
    id: int
    projectID: int
    createdAt: datetime

    class Config:
        from_attributes = True


class ProjectResponse(ProjectBase):
    id: int
    # Jumlah seluruh baris kontrak yang belum dihapus.
    contractValue: Decimal = Decimal(0)
    contractCount: int = 0
    createdAt: datetime
    updatedAt: Optional[datetime] = None

    class Config:
        from_attributes = True
