"""Muatan permintaan untuk modul rekrutmen."""

from datetime import date
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


class NilaiSoal(BaseModel):
    """
    Nilai satu soal.

    `score` boleh `None`, dan itu BUKAN nol: `None` membatalkan penilaian
    yang terlanjur keliru, nol adalah keputusan bahwa jawabannya salah.
    Batas atasnya tidak ditulis di sini — `maxScore` berbeda per soal dan
    dibaca dari basis data, bukan dipercaya dari muatan.
    """

    questionID: int
    score: Optional[int] = Field(None, ge=0)
    checkerNote: Optional[str] = Field(None, max_length=500)


class PenilaianBatch(BaseModel):
    """
    Penilaian beberapa soal sekaligus.

    Yang memeriksa membaca seluruh lembar lalu menekan Simpan satu kali.
    Batas 200 sejalan dengan batas pendaftaran pelamar; paket ujian terpanjang
    di sistem ini puluhan soal, bukan ratusan.
    """

    nilai: list[NilaiSoal] = Field(..., min_length=1, max_length=200)


class UjianBaru(BaseModel):
    """
    Paket ujian baru.

    Batas durasi 5–480 menit. Bawahnya menjaga salah ketik yang membuat
    ujian berakhir sebelum pelamarnya sempat membaca soal pertama; atasnya
    delapan jam, lebih panjang daripada hari kerja mana pun.
    """

    name: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    durationMinutes: int = Field(90, ge=5, le=480)
    isActive: bool = True


class UjianUbah(BaseModel):
    """
    Perubahan paket ujian; seluruh bidang opsional.

    `durationMinutes` DITOLAK selagi ada pelamar yang sedang mengerjakan —
    lihat `HrRecruitmentRepository.ubah_ujian`. Penjagaannya di repository,
    bukan di sini, karena ia menuntut pembacaan basis data.
    """

    name: Optional[str] = Field(None, min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    durationMinutes: Optional[int] = Field(None, ge=5, le=480)
    isActive: Optional[bool] = None


class StatusPelamar(BaseModel):
    """
    Status yang DIPUTUSKAN MANUSIA.

    Daftar sahnya ditegakkan repository, bukan di sini: `baru`,
    `mengerjakan`, `selesai`, dan `dinilai` disimpulkan dari keadaan
    dokumennya, dan menolaknya di lapisan skema akan menyembunyikan sebab
    penolakannya di balik 422 yang tidak menyebutkan apa pun.
    """

    status: str = Field(..., min_length=3, max_length=20)


class BiodataPelamar(BaseModel):
    """
    Biodata yang diisi pelamar sendiri lewat tautannya.

    SELURUHNYA opsional. Pelamar yang tidak punya surel tetap harus dapat
    mengerjakan ujiannya — mewajibkannya di sini berarti menutup ujian bagi
    orang yang justru hendak diuji.

    `name` TIDAK ada di sini: ia dimasukkan HR saat mendaftarkan, dan
    dipakai mencocokkan lembar dengan orangnya.
    """

    nickName: Optional[str] = Field(None, max_length=50)
    dateOfBirth: Optional[date] = None
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    phoneNumber: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=150)
