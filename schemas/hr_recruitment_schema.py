"""Muatan permintaan untuk modul rekrutmen."""

from typing import Optional

from pydantic import BaseModel, Field


class SoalCreate(BaseModel):
    """
    Soal baru.

    Panjang dibatasi walaupun kolomnya `TEXT`: isian tanpa batas membuat satu
    orang dapat menyimpan berkilo-kilo teks tanpa disengaja, dan soal terpanjang
    yang dipindahkan dari sistem lama hanya 383 karakter.
    """

    testID: int
    question: str = Field(..., min_length=5, max_length=2000)
    notes: Optional[str] = Field(None, max_length=500)
    # Lampiran berupa HTML — tabel berat besi, gambar potongan.
    attachment: Optional[str] = Field(None, max_length=4000)
    category: Optional[str] = Field("civil", max_length=30)
    maxScore: Optional[int] = Field(5, ge=1, le=100)
    allowsUpload: Optional[bool] = False


class SoalUpdate(BaseModel):
    """
    Perubahan soal; seluruh isian opsional.

    Yang tidak dikirim tidak tersentuh — mengirim seluruh kolom pada setiap
    penyuntingan membuat perubahan yang tidak disengaja ikut tersimpan.
    """

    question: Optional[str] = Field(None, min_length=5, max_length=2000)
    notes: Optional[str] = Field(None, max_length=500)
    attachment: Optional[str] = Field(None, max_length=4000)
    category: Optional[str] = Field(None, max_length=30)
    maxScore: Optional[int] = Field(None, ge=1, le=100)
    allowsUpload: Optional[bool] = None
    sortOrder: Optional[int] = Field(None, ge=0)
