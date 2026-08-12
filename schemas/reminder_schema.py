from datetime import date as d
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from models.reminder_model import REMINDER_CATEGORIES


class ReminderBase(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    note: Optional[str] = Field(default=None, max_length=500)
    date: d
    category: str = Field(default="Lainnya")
    # Untuk seluruh pengguna. Hanya akses 4 ke atas yang boleh mengisi True;
    # pemeriksaannya di controller, bukan di sini.
    isShared: bool = False
    # Orang yang ditandai. Kosong berarti hanya pembuatnya yang melihat.
    targets: List[int] = Field(default_factory=list)

    @field_validator("category")
    @classmethod
    def kategori_dikenali(cls, v: str) -> str:
        """
        Kategori harus salah satu dari daftar tetap.

        Ditolak di sini, bukan dibiarkan tersimpan apa adanya: satu ketikan
        bebas yang lolos akan muncul sebagai kategori tersendiri pada
        penyaring, dan sejak itu daftarnya tidak lagi dapat dipercaya.
        """
        if v not in REMINDER_CATEGORIES:
            raise ValueError(
                f"Kategori tidak dikenali. Pilih salah satu: "
                f"{', '.join(REMINDER_CATEGORIES)}"
            )
        return v


class ReminderCreate(ReminderBase):
    pass


class ReminderUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=150)
    note: Optional[str] = Field(default=None, max_length=500)
    date: Optional[d] = None
    category: Optional[str] = None
    isShared: Optional[bool] = None
    # `None` berarti daftar tandaan tidak diubah; daftar kosong melepas
    # seluruh tandaan.
    targets: Optional[List[int]] = None

    @field_validator("category")
    @classmethod
    def kategori_dikenali(cls, v):
        if v is None:
            return v
        if v not in REMINDER_CATEGORIES:
            raise ValueError(
                f"Kategori tidak dikenali. Pilih salah satu: "
                f"{', '.join(REMINDER_CATEGORIES)}"
            )
        return v
