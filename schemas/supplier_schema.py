from pydantic import BaseModel, EmailStr, StringConstraints, field_validator, ConfigDict
from typing import Annotated, Optional
from datetime import datetime as dt

class SupplierBase(BaseModel):
    prefix: Annotated[str, StringConstraints(min_length=1, max_length=25)] | None = None
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    address: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    city: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    province: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    phoneNumber: Annotated[str, StringConstraints(pattern=r"^[0-9]{10,20}$")]
    email: Annotated[EmailStr, StringConstraints(max_length=255)] | None = None
    npwp: Annotated[str, StringConstraints(pattern=r"^\d{16}$")] | None = None
    itemsSold: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    serviceArea: Annotated[str, StringConstraints(min_length=1, max_length=255)]

class SupplierCreate(SupplierBase):
    createdBy: int | None = None

class SupplierUpdate(SupplierBase):
    id: int
    updatedBy: int | None = None

class SupplierResponse(SupplierBase):
    """
    Bentuk jawaban; polanya SENGAJA dilonggarkan.

    `SupplierBase` menuntut telepon 10–20 angka dan NPWP persis 16 digit.
    Aturan itu tepat ketika data BARU diisi, tetapi salah bila dipakai
    MEMBACA: basis data memuat pemasok lama yang telepon atau NPWP-nya tidak
    memenuhi pola tersebut — sebagian dimasukkan sebelum aturannya ada,
    sebagian memang tidak punya.

    Menolaknya saat membaca membuat SELURUH permintaan gagal dengan 500 yang
    tidak menyebut sebabnya. Purchase order yang pemasoknya begitu tidak
    dapat dibuka sama sekali, dan yang membukanya menyimpulkan dokumennya
    rusak.

    Sudah terjadi: PO 225 tidak dapat dibuka karena satu bidang pemasoknya.
    """

    model_config = ConfigDict(from_attributes=True)

    # Dinyatakan ulang TANPA pola.
    #
    # Data yang sudah ada dibaca apa adanya; yang menyaringnya saat pembuatan
    # tetap `SupplierCreate` dan `SupplierUpdate`.
    phoneNumber: str | None = None
    npwp: str | None = None
    prefix: str | None = None
    address: str | None = None
    city: str | None = None
    province: str | None = None
    itemsSold: str | None = None
    serviceArea: str | None = None
    # Surel lama sebagian tidak berbentuk alamat yang sah; `EmailStr`
    # menolaknya dan menggagalkan pembacaan.
    email: str | None = None
    
    id: int
    createdBy: int | None = None
    createdAt: dt | None = None
    updatedBy: int | None = None
    updatedAt: dt | None = None
    deletedAt: dt | None = None
    deletedBy: int | None = None
    isDelete: bool = False
    isBlacklist: bool = False
    blacklistReason: str | None = None
    blacklistedBy: int | None = None
    blacklistedAt: dt | None = None

class SupplierSearchDocument(BaseModel):
    id: int
    name: str
    address: str
    city: str
    province: str
    phoneNumber: str
    email: Optional[str] = None
    npwp: Optional[str] = None
    itemsSold: list[str]
    serviceArea: list[str]
    isBlacklist: bool = False
    blacklistReason: Optional[str] = None

class SupplierBlacklistUpdate(BaseModel):
    isBlacklist: bool
    blacklistReason: Annotated[str, StringConstraints(max_length=500)] | None = None