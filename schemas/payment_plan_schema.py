"""
Skema rencana pengeluaran.

Catatan yang berlaku pada `PaymentPlanUpdate`: ia menyebut bidangnya SATU PER
SATU dan tidak mewarisi `PaymentPlanBase`, supaya semuanya opsional. Kolom
baru karena itu harus ditambahkan di DUA tempat — Pydantic membuang bidang
yang tidak dikenalnya tanpa galat apa pun. `skemacek.py` menjaganya.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

#: Pengelompokan pengeluaran.
#:
#: Dipakai pada ringkasan bulanan; tanpa itu daftarnya hanya deretan angka
#: yang tidak menjelaskan ke mana kasnya pergi.
KATEGORI_KELUAR = {
    "material",
    "subkon",
    "gaji",
    "operasional",
    "pajak",
    # Angsuran dan pelunasan utang.
    #
    # Tandingan dari `pinjaman` di sisi pemasukan: uang yang masuk sebagai
    # pencairan keluar lagi sebagai angsuran, dan tanpa kategorinya sendiri
    # ia tertimbun di "lain-lain" — padahal justru itu yang perlu terlihat
    # saat menilai apakah kasnya cukup.
    "utang",
    "lain",
}

#: Pengelompokan pemasukan.
#:
#: Berbeda sama sekali dari pengeluaran: uang masuk tidak dibelanjakan untuk
#: material atau gaji, ia DATANG dari tagihan proyek, uang muka, atau
#: pengembalian pajak. Memakai satu daftar untuk keduanya membuat layar
#: menawarkan "gaji" sebagai sumber pemasukan.
#: `restitusi` sengaja TIDAK ada.
#:
#: Restitusi pajak praktis tidak pernah terjadi di sini; menawarkannya hanya
#: memanjangkan daftar dengan pilihan yang tidak pernah ditekan.
KATEGORI_MASUK = {"tagihan", "uangmuka", "retensi", "pinjaman", "lain"}

#: Gabungan keduanya; dipakai validator yang belum tahu arahnya.
KATEGORI = KATEGORI_KELUAR | KATEGORI_MASUK

#: Keadaan rencana.
STATUS = {"rencana", "terpakai", "batal"}


#: Arah aliran kas.
ARAH = {"keluar", "masuk"}


class PaymentPlanBase(BaseModel):
    # `keluar` atau `masuk`; menentukan tandanya pada perhitungan kas.
    planType: str = "keluar"
    date: date
    amount: Decimal = Field(gt=0)
    description: str = Field(min_length=1, max_length=255)
    category: Optional[str] = None
    projectName: Optional[str] = Field(default=None, max_length=255)
    bankAccountID: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("category")
    @classmethod
    def kategori_dikenal(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in KATEGORI:
            raise ValueError(f"category harus salah satu dari {sorted(KATEGORI)}")
        return v

    @field_validator("planType")
    @classmethod
    def arah_dikenal(cls, v: str) -> str:
        if v not in ARAH:
            raise ValueError(f"planType harus salah satu dari {sorted(ARAH)}")
        return v

    @model_validator(mode="after")
    def kategori_cocok_arahnya(self):
        """
        Kategori harus berasal dari daftar yang sesuai arahnya.

        Diperiksa di SERVER, bukan cukup dengan menyaring pilihan di layar:
        muatan permintaan dapat disusun sendiri, dan kategori yang tidak
        cocok membuat ringkasan menampilkan "gaji" sebagai sumber pemasukan.
        """
        if self.category is None:
            return self
        sah = KATEGORI_MASUK if self.planType == "masuk" else KATEGORI_KELUAR
        if self.category not in sah:
            raise ValueError(
                f"category '{self.category}' tidak berlaku untuk "
                f"planType '{self.planType}'; pilih dari {sorted(sah)}"
            )
        return self


class PaymentPlanCreate(PaymentPlanBase):
    pass


class PaymentPlanUpdate(BaseModel):
    # PENTING: tidak mewarisi `PaymentPlanBase`; lihat catatan berkas.
    planType: Optional[str] = None
    date: Optional[date] = None
    amount: Optional[Decimal] = Field(default=None, gt=0)
    description: Optional[str] = Field(default=None, min_length=1, max_length=255)
    category: Optional[str] = None
    projectName: Optional[str] = Field(default=None, max_length=255)
    bankAccountID: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[str] = None

    @field_validator("category")
    @classmethod
    def kategori_dikenal(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in KATEGORI:
            raise ValueError(f"category harus salah satu dari {sorted(KATEGORI)}")
        return v

    @field_validator("status")
    @classmethod
    def status_dikenal(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in STATUS:
            raise ValueError(f"status harus salah satu dari {sorted(STATUS)}")
        return v


class PaymentPlanResponse(PaymentPlanBase):
    id: int
    status: str
    createdAt: datetime
    updatedAt: Optional[datetime] = None
