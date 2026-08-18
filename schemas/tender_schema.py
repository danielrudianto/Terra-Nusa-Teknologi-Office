"""
Skema tender pengadaan.

Catatan yang berlaku untuk seluruh skema `*Update` di berkas ini: masing-masing
menyebut bidangnya SATU PER SATU dan tidak mewarisi `*Base`, supaya semuanya
opsional. Konsekuensinya kolom baru harus ditambahkan di DUA tempat — Pydantic
membuang bidang yang tidak dikenalnya tanpa galat apa pun, sehingga muatan yang
benar tersimpan sebagai NULL dan jawabannya tetap sukses.

`skemacek.py` menjaga agar hal itu tidak terlewat.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

#: Jenis tender yang dikenal.
#:
#: Menentukan bentuk barisnya: `barang` diambil dari katalog dengan satuan dan
#: volume; `jasa` ditulis bebas sebagai uraian pekerjaan.
JENIS_TENDER = {"barang", "jasa"}

#: Keadaan tender.
#:
#: `draft` masih disusun · `berjalan` sudah disebar · `selesai` pemenang sudah
#: dipilih · `batal` dihentikan tanpa pemenang.
STATUS_TENDER = {"draft", "berjalan", "selesai", "batal"}


class TenderItemBase(BaseModel):
    """Satu baris permintaan: barang yang dicari atau pekerjaan yang dipesan."""

    itemID: Optional[int] = None
    name: str = Field(min_length=1, max_length=255)
    specification: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = Field(default=None, max_length=50)
    sortOrder: int = 0


class TenderBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    date: date
    tenderType: str
    projectName: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    paymentTerm: Optional[str] = Field(default=None, max_length=20)
    creditTerm: Optional[int] = None
    requirements: Optional[str] = None
    dueDate: Optional[date] = None

    @field_validator("tenderType")
    @classmethod
    def jenis_dikenal(cls, v: str) -> str:
        if v not in JENIS_TENDER:
            raise ValueError(
                f"tenderType harus salah satu dari {sorted(JENIS_TENDER)}"
            )
        return v


class TenderCreate(TenderBase):
    """
    Baris permintaan ikut dikirim bersama tendernya.

    Tender tanpa satu pun baris tidak dapat disebarkan — tidak ada yang bisa
    ditawar. Diperiksa di sini, bukan saat menyebarkan, supaya kesalahannya
    terlihat saat masih mengisi.
    """

    items: List[TenderItemBase] = Field(min_length=1)


class TenderUpdate(BaseModel):
    # PENTING: tidak mewarisi `TenderBase`; lihat catatan berkas.
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    date: Optional[date] = None
    tenderType: Optional[str] = None
    projectName: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    paymentTerm: Optional[str] = Field(default=None, max_length=20)
    creditTerm: Optional[int] = None
    requirements: Optional[str] = None
    dueDate: Optional[date] = None
    # Baris diganti seluruhnya bila disebutkan; kosong berarti tidak diubah.
    items: Optional[List[TenderItemBase]] = None

    @field_validator("tenderType")
    @classmethod
    def jenis_dikenal(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in JENIS_TENDER:
            raise ValueError(
                f"tenderType harus salah satu dari {sorted(JENIS_TENDER)}"
            )
        return v


class TenderQuoteItemBase(BaseModel):
    """
    Harga satu baris pada satu penawaran.

    `price` boleh KOSONG — tidak setiap pemasok menawar seluruh baris. Kosong
    berbeda dari nol: nol berarti digratiskan, kosong berarti tidak ditawar,
    dan yang tidak menawar tidak boleh terhitung sebagai yang termurah.
    """

    tenderItemID: int
    price: Optional[Decimal] = None
    notes: Optional[str] = None


class TenderQuoteBase(BaseModel):
    supplierID: int
    paymentTerm: Optional[str] = Field(default=None, max_length=20)
    creditTerm: Optional[int] = None
    # Apakah pemasok memungut PPN; menentukan biaya sebenarnya.
    #
    # PPN yang dipungut PKP dapat dikreditkan, sehingga yang menjadi beban
    # hanya DPP. Pemasok non-PKP tidak memungut apa pun — dan seluruh
    # harganya menjadi biaya.
    includePpn: bool = False
    ppnPercentage: Optional[Decimal] = None
    # `franco` (diantar pemasok) atau `loco` (diambil sendiri).
    #
    # Loco berarti AKN menanggung angkutnya, dan ongkos itu tidak pernah
    # muncul di surat penawaran mana pun.
    deliveryMethod: Optional[str] = None
    # Biaya lain yang ditanggung AKN di luar harga barangnya.
    otherCost: Optional[Decimal] = None
    otherCostNote: Optional[str] = None
    notes: Optional[str] = None
    quotedAt: Optional[date] = None
    items: List[TenderQuoteItemBase] = []


#: Cara pengiriman yang dikenal.
METODE_KIRIM = {"franco", "loco"}


class TenderQuoteCreate(TenderQuoteBase):
    @field_validator("deliveryMethod")
    @classmethod
    def metode_dikenal(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in METODE_KIRIM:
            raise ValueError(
                f"deliveryMethod harus salah satu dari {sorted(METODE_KIRIM)}"
            )
        return v


class TenderQuoteUpdate(BaseModel):
    # PENTING: tidak mewarisi `TenderQuoteBase`; lihat catatan berkas.
    supplierID: Optional[int] = None
    paymentTerm: Optional[str] = Field(default=None, max_length=20)
    creditTerm: Optional[int] = None
    includePpn: Optional[bool] = None
    ppnPercentage: Optional[Decimal] = None
    deliveryMethod: Optional[str] = None
    otherCost: Optional[Decimal] = None
    otherCostNote: Optional[str] = None
    notes: Optional[str] = None
    quotedAt: Optional[date] = None
    items: Optional[List[TenderQuoteItemBase]] = None


class TenderPemenang(BaseModel):
    """
    Penetapan pemenang.

    Alasannya WAJIB, bukan opsional: pemenang tidak selalu yang termurah —
    waktu kirim, garansi, dan riwayat pemasok ikut menentukan. Tanpa alasan
    tertulis, keputusannya tidak dapat ditinjau siapa pun setelah orangnya
    berganti.
    """

    winnerQuoteID: int
    winnerReason: str = Field(min_length=10, max_length=1000)


class TenderResponse(TenderBase):
    id: int
    number: Optional[int] = None
    status: str
    winnerQuoteID: Optional[int] = None
    winnerReason: Optional[str] = None
    decidedAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: Optional[datetime] = None
