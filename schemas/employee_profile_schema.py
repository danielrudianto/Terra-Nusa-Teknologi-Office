from datetime import date
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class RiwayatPendidikan(BaseModel):
    """Satu baris pendidikan formal."""

    level: Optional[str] = Field(None, max_length=50)
    school: Optional[str] = Field(None, max_length=200)
    major: Optional[str] = Field(None, max_length=150)
    fromYear: Optional[str] = Field(None, max_length=10)
    toYear: Optional[str] = Field(None, max_length=10)
    gpa: Optional[str] = Field(None, max_length=10)


class RiwayatKerja(BaseModel):
    """Satu baris pengalaman kerja sebelum masuk."""

    company: Optional[str] = Field(None, max_length=200)
    field: Optional[str] = Field(None, max_length=150)
    position: Optional[str] = Field(None, max_length=150)
    fromDate: Optional[str] = Field(None, max_length=20)
    toDate: Optional[str] = Field(None, max_length=20)
    reasonLeaving: Optional[str] = Field(None, max_length=500)


class Bahasa(BaseModel):
    """Satu baris kemampuan bahasa."""

    language: Optional[str] = Field(None, max_length=50)
    # 'aktif' | 'pasif' | '' — dua kemampuan yang berbeda, dicatat terpisah
    # karena banyak orang mampu membaca tetapi tidak berbicara.
    speaking: Optional[str] = Field(None, max_length=10)
    writing: Optional[str] = Field(None, max_length=10)


class AnggotaKeluarga(BaseModel):
    """Satu baris susunan keluarga, seperti pada kartu keluarga."""

    relation: Optional[str] = Field(None, max_length=30)
    name: Optional[str] = Field(None, max_length=150)
    birthday: Optional[str] = Field(None, max_length=20)
    education: Optional[str] = Field(None, max_length=50)
    job: Optional[str] = Field(None, max_length=100)


class SuratIzinMengemudi(BaseModel):
    """
    Satu SIM: golongan beserta NOMORNYA.

    Bukan sekadar daftar golongan yang dimiliki. Tiap golongan diterbitkan
    sebagai kartu tersendiri dengan nomornya sendiri, dan yang diperlukan
    saat mengurus perizinan maupun penugasan mengemudi adalah nomornya —
    mengetahui seseorang "punya SIM A" tanpa nomornya tidak menyelesaikan
    apa pun.
    """

    # A, B1, B2, C. Golongan D tidak dipakai di sini.
    golongan: Optional[str] = Field(None, max_length=5)
    nomor: Optional[str] = Field(None, max_length=30)


class EmployeeProfileSave(BaseModel):
    """
    Muatan penyimpanan profil.

    Seluruh isian OPSIONAL. Profil diisi bertahap — sebagian datanya baru
    tersedia setelah karyawannya masuk, dan menolak simpan karena satu kolom
    belum terisi membuat yang sudah diketik ikut hilang.

    Panjang tiap isian dibatasi mengikuti kolomnya di basis data, agar isian
    terlalu panjang ditolak dengan pesan yang jelas — bukan oleh MySQL dengan
    galat yang tidak menyebut kolomnya.
    """

    birthPlace: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=10)
    bloodType: Optional[str] = Field(None, max_length=5)
    religion: Optional[str] = Field(None, max_length=30)
    maritalStatus: Optional[str] = Field(None, max_length=20)
    motherName: Optional[str] = Field(None, max_length=150)
    fatherName: Optional[str] = Field(None, max_length=150)
    citizenship: Optional[str] = Field(None, max_length=50)
    ethnicity: Optional[str] = Field(None, max_length=50)
    # Batas atas wajar; bukan aturan medis, hanya penjaga salah ketik.
    heightCm: Optional[int] = Field(None, ge=0, le=300)
    weightKg: Optional[int] = Field(None, ge=0, le=500)

    # `ktpNumber` dibuang: NIK sudah di `employees.nik`.
    ktpAddress: Optional[str] = Field(None, max_length=500)
    ktpValidUntil: Optional[date] = None
    drivingLicenses: Optional[List[SuratIzinMengemudi]] = None

    # Alamat tinggal, HP, dan surel dibuang: sudah di `employees`.
    homeOwnership: Optional[str] = Field(None, max_length=30)
    homePhone: Optional[str] = Field(None, max_length=30)

    bpjsKesehatan: Optional[str] = Field(None, max_length=30)
    bpjsKetenagakerjaan: Optional[str] = Field(None, max_length=30)

    bankName: Optional[str] = Field(None, max_length=100)
    bankAccountName: Optional[str] = Field(None, max_length=100)
    bankAccountNumber: Optional[str] = Field(None, max_length=50)

    formalEducation: Optional[List[RiwayatPendidikan]] = None
    workExperience: Optional[List[RiwayatKerja]] = None
    languages: Optional[List[Bahasa]] = None
    familyMembers: Optional[List[AnggotaKeluarga]] = None


class EmployeeProfileResponse(BaseModel):
    id: int
    employeeID: int

    class Config:
        from_attributes = True
        extra = "allow"
