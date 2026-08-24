"""
Bentuk muatan Certificate of Payment.

Yang TIDAK ada di sini disengaja: `price` dan `amount`.

Bila layar boleh mengirim harga, maka harga harus lebih dulu sampai ke layar
— dan orang lapangan tidak boleh mengetahuinya. Keduanya disusun di server
dari baris SPK; menerimanya dari luar hanya membuka jalan menagih pada harga
yang tidak pernah disepakati.
"""

from datetime import date as date_type
from typing import List, Optional

from pydantic import BaseModel, Field


class CoPItemInput(BaseModel):
    """Satu baris pekerjaan yang disertifikasi."""

    purchaseOrderItemID: int
    # Satu-satunya angka yang datang dari lapangan.
    #
    # `gt=0` bukan `ge=0`: baris bervolume nol tidak menyatakan apa pun dan
    # hanya memanjangkan dokumen. Yang batal dikerjakan dihapus barisnya.
    quantity: float = Field(gt=0)
    remarks: Optional[str] = None


class CoPCreate(BaseModel):
    purchaseOrderID: int
    date: date_type
    periodStart: Optional[date_type] = None
    periodEnd: Optional[date_type] = None
    projectName: Optional[str] = None
    note: Optional[str] = None
    items: List[CoPItemInput] = Field(min_length=1)


class CoPUpdate(BaseModel):
    date: Optional[date_type] = None
    periodStart: Optional[date_type] = None
    periodEnd: Optional[date_type] = None
    note: Optional[str] = None
    # `None` berarti "jangan sentuh barisnya"; daftar kosong ditolak
    # controller — CoP tanpa baris tidak menyatakan progres apa pun.
    items: Optional[List[CoPItemInput]] = None


class CoPAdjustmentInput(BaseModel):
    """
    Satu baris potongan atau tambahan.

    `amount` SELALU positif; arahnya ditentukan `kind`. Nominal bertanda
    minus adalah cara paling mudah membuat potongan terjumlah sebagai
    tambahan tanpa ada yang menyadarinya, jadi tandanya tidak pernah
    diserahkan kepada nilainya.
    """

    kind: str = Field(pattern="^(deduction|addition)$")
    category: str
    # Wajib bila `category` = "lain_lain"; ditegakkan controller supaya
    # pesannya dapat menyebut baris mana yang kosong.
    label: Optional[str] = None
    amount: float = Field(gt=0)
    note: Optional[str] = None


class CoPAdjustmentSet(BaseModel):
    """
    Keadaan AKHIR seluruh penyesuaian CoP.

    Dikirim utuh, bukan per baris: layar mengirimkan susunan yang
    dikehendaki, dan server menggantinya seluruhnya. Menyamakan baris demi
    baris hanya menambah jalan bagi keduanya untuk berselisih.
    """

    adjustments: List[CoPAdjustmentInput] = Field(default_factory=list)
