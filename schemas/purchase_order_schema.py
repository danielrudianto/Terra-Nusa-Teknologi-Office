from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import date as date_type, datetime
from enum import Enum


class PurchaseOrderStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PurchaseOrderBase(BaseModel):
    date: date_type
    supplierID: int
    purchaseType: str
    templateVersion: str
    projectName: str
    dpp: float = Field(ge=0)
    ppn: float = Field(ge=0, default=0.00)
    status: PurchaseOrderStatus = PurchaseOrderStatus.DRAFT
    # Flexible JSON payloads (line items, addresses, PIC contacts, delivery term)
    customData: Optional[Dict[str, Any]] = None
    billing_requirements: Dict[str, Any] = Field(default_factory=dict)
    payment_term: str = "CASH"
    note: Optional[str] = None


class PurchaseOrderCreate(PurchaseOrderBase):
    # Hanya dipakai untuk membentuk nomor dokumen (mis. "MICZ" -> 025-SPK-MICZ-G).
    # Not persisted as a column.
    projectCode: Optional[str] = None
    # Dokumen induk, bila yang dibuat adalah ADENDUM.
    #
    # Nomor adendumnya TIDAK dikirim dari layar: server yang menghitungnya
    # dari adendum yang sudah ada untuk induk tersebut. Membiarkan layar
    # menentukannya membuka kemungkinan dua adendum bernomor sama saat dua
    # orang membuatnya bersamaan.
    parentPurchaseOrderID: Optional[int] = None
    # If provided, use this exact PO number instead of auto-generating.
    name: Optional[str] = None
    # Baris item PO. WAJIB ada di schema: route memanggil `.dict()`, sehingga
    # field yang tidak dideklarasikan di sini akan dibuang sebelum sampai ke
    # controller — itulah sebabnya purchase_order_items selalu kosong.
    items: Optional[List[Dict[str, Any]]] = None
    pphCode: Optional[str] = None
    pphTaxObject: Optional[str] = None
    pphPercentage: Optional[float] = None


class PurchaseOrderUpdate(BaseModel):
    date: Optional[date_type] = None
    supplierID: Optional[int] = None
    purchaseType: Optional[str] = None
    templateVersion: Optional[str] = None
    projectName: Optional[str] = None
    dpp: Optional[float] = Field(default=None, ge=0)
    ppn: Optional[float] = Field(default=None, ge=0)
    status: Optional[PurchaseOrderStatus] = None
    customData: Optional[Dict[str, Any]] = None
    billing_requirements: Optional[Dict[str, Any]] = None
    payment_term: Optional[str] = None
    note: Optional[str] = None


class PurchaseOrderResponse(BaseModel):
    id: int
    date: date_type
    supplierID: int
    name: str
    purchaseType: str
    templateVersion: str
    projectName: str
    dpp: float
    ppn: float
    status: Optional[str] = None
    customData: Optional[Dict[str, Any]] = None
    billing_requirements: Optional[Dict[str, Any]] = None
    payment_term: Optional[str] = None
    note: Optional[str] = None
    revision: Optional[int] = 0
    isApproved: Optional[bool] = False
    approvedBy: Optional[int] = None
    approvedAt: Optional[datetime] = None
    createdBy: Optional[int] = None
    createdAt: Optional[datetime] = None
    # Dipakai saat mencetak ulang dokumen: tanpa field ini FastAPI membuang
    # item dan data supplier dari response.
    number: Optional[int] = None
    items: Optional[List[Dict[str, Any]]] = None
    pphCode: Optional[str] = None
    pphTaxObject: Optional[str] = None
    pphPercentage: Optional[float] = None
    supplierName: Optional[str] = None
    supplierPrefix: Optional[str] = None
    supplierAddress: Optional[str] = None
    supplierCity: Optional[str] = None
    supplierNpwp: Optional[str] = None
    # Hasil join di daftar PO (snake_case, sesuai label kolom query)
    supplier_name: Optional[str] = None
    supplier_prefix: Optional[str] = None
    isDelete: Optional[bool] = False
    deletedBy: Optional[int] = None
    deletedAt: Optional[datetime] = None
    # Nama dan jabatan penyetuju, diambil lewat sambungan ke tabel pengguna.
    #
    # Tanpa didaftarkan di sini FastAPI membuangnya dari jawaban —
    # `response_model` menyaring bidang yang tidak dikenalnya, tanpa galat
    # maupun peringatan. Blok tanda tangan pada dokumen karena itu selalu
    # kosong, walaupun dokumennya sudah disetujui.
    approvedByName: Optional[str] = None
    approvedByPosition: Optional[str] = None

    class Config:
        from_attributes = True


class CreatePurchaseOrderResponse(BaseModel):
    message: str
    purchase_order_id: int
    purchase_order_name: str


class PurchaseOrderListResponse(BaseModel):
    data: List[PurchaseOrderResponse]
    count: int


class ErrorResponse(BaseModel):
    error: str
    status: int