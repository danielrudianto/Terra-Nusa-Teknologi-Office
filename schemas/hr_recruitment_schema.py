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


class PelamarBaru(BaseModel):
    """Satu pelamar; hanya nama dan jenis kelamin."""

    name: str = Field(..., min_length=2, max_length=150)
    # L atau P; kosong diterima — sebagian nama tidak menyiratkan keduanya,
    # dan menebaknya lebih buruk daripada membiarkannya kosong.
    gender: Optional[str] = Field(None, max_length=1)


class PelamarBatch(BaseModel):
    """
    Pendaftaran beberapa pelamar sekaligus.

    Dibatasi 200 sekali kirim: satu gelombang rekrutmen tidak pernah sebesar
    itu, dan muatan tanpa batas membuat satu permintaan dapat menerbitkan
    token tanpa henti.
    """

    testID: int
    orang: list[PelamarBaru] = Field(..., min_length=1, max_length=200)
    # Masa berlaku tautan, dalam hari.
    berlakuHari: Optional[int] = Field(7, ge=1, le=30)
