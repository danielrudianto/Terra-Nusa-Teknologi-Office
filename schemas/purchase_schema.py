from pydantic import BaseModel, Field
from datetime import datetime as dt, date as d
from typing import Optional

class PurchaseBase(BaseModel):
    invoiceName: str = Field(..., description="Name of the invoice")
    receiptName: str = Field(..., description="Name of the receipt")
    taxInvoiceName: Optional[str] = Field(None, description="Name of the tax invoice")
    supplierID: int = Field(..., description="ID of the supplier")
    date: d = Field(..., description="Date of the purchase")
    dueDate: Optional[d] = Field(None, description="Due date of the purchase")
    purchaseOrderName: str = Field(..., description="Name of the purchase order")
    projectName: str = Field(..., description="Name of the project")
    purchaseType: str = Field(..., description="Type of the purchase")
    procurementType: str = Field(..., description="Type of procurement (either goods or other)")
    dpp: float = Field(..., ge=0, description="DPP value")
    ppn: float = Field(..., ge=0, description="PPN value")
    pbbkb: float = Field(..., ge=0, description="PBBKB value")
    pphCode: Optional[str] = Field(None, description="PPH code")
    pphTaxObject: Optional[str] = Field(None, description="PPH tax object")
    pphPercentage: float = Field(..., ge=0, le=16, description="PPH percentage")
    otherValue: Optional[float] = Field(None, description="Other value")
    otherValueNote: Optional[str] = Field(None, description="Note for other value")
    isInvoiceAttached: bool = Field(..., description="Flag to indicate if the invoice is attached")
    isReceiptAttached: bool = Field(..., description="Flag to indicate if the receipt is attached")
    isTaxInvoiceAttached: bool = Field(..., description="Flag to indicate if the tax invoice is attached")
    isCopAttached: bool = Field(..., description="Flag to indicate if the COP is attached")
    isCopyPurchaseOrderAttached: bool = Field(..., description="Flag to indicate if the copy purchase order is attached")
    bankName: str = Field(..., description="Name of the bank")
    bankAccountName: str = Field(..., description="Name of the bank account")
    bankAccountNumber: str = Field(..., description="Bank account number")
    paymentMethod: str = Field(..., description="Payment method")
    lastStatus: str = Field(..., description="Last status of the purchase")
    lastStatusDescription: Optional[str] = Field(None, description="Last status description")
    isInternal: bool = Field(False, description="Whether the purchase is internal")
    # Certificate of payment yang ditagihkan pembelian ini.
    #
    # Opsional, dan memang mayoritas kosong: pembelian barang tidak melewati
    # certificate of payment sama sekali. Bila terisi, server memastikan
    # CoP-nya sudah disetujui dan belum pernah ditagihkan.
    certificateOfPaymentID: Optional[int] = Field(
        None, description="Certificate of payment being billed by this purchase"
    )

class PurchaseCreate(PurchaseBase):
    pass

class PurchaseUpdate(BaseModel):
    invoiceName: Optional[str] = None
    receiptName: Optional[str] = None
    taxInvoiceName: Optional[str] = None
    supplierID: Optional[int] = None
    date: Optional[d] = None
    dueDate: Optional[d] = None
    purchaseOrderName: Optional[str] = None
    projectName: Optional[str] = None
    purchaseType: Optional[str] = None
    procurementType: Optional[str] = None
    dpp: Optional[float] = None
    ppn: Optional[float] = None
    pbbkb: Optional[float] = None
    pphCode: Optional[str] = None
    pphTaxObject: Optional[str] = None
    pphPercentage: Optional[float] = None
    otherValue: Optional[float] = None
    otherValueNote: Optional[str] = None
    isInvoiceAttached: Optional[bool] = None
    isReceiptAttached: Optional[bool] = None
    isTaxInvoiceAttached: Optional[bool] = None
    isCopAttached: Optional[bool] = None
    isCopyPurchaseOrderAttached: Optional[bool] = None
    bankName: Optional[str] = None
    bankAccountName: Optional[str] = None
    bankAccountNumber: Optional[str] = None
    paymentMethod: Optional[str] = None
    lastStatus: Optional[str] = None
    lastStatusDescription: Optional[str] = None
    isInternal: Optional[bool] = None
    updatedBy: Optional[int] = None
    updatedAt: Optional[dt] = None

class PurchaseResponse(PurchaseBase):
    id: int
    isPaid: bool
    isDelete: bool
    createdAt: dt
    updatedAt: Optional[dt] = None
    deletedAt: Optional[dt] = None
    createdBy: int
    updatedBy: Optional[int] = None
    deletedBy: Optional[int] = None
    supplier: Optional[dict] = None
    # Id dokumen purchase order, bila nomornya cocok dengan dokumen yang ada.
    #
    # Kuerinya sudah menyertakannya lewat sambungan nama, tetapi tanpa
    # didaftarkan di sini FastAPI MEMBUANGNYA dari jawaban — `response_model`
    # menyaring bidang yang tidak dikenalnya, tanpa galat maupun peringatan.
    #
    # Akibatnya daftar pembelian menandai SELURUH barisnya "dokumen belum
    # tersedia", termasuk yang dokumennya benar-benar ada.
    purchase_order_id: Optional[int] = None

    class Config:
        from_attributes = True

class PurchaseListResponse(BaseModel):
    data: list[PurchaseResponse]
    count: int

class PurchaseStatusBase(BaseModel):
    status: str = Field(..., description="Status of the purchase")
    description: Optional[str] = Field(None, description="Description of the status")

class PurchaseStatusCreate(PurchaseStatusBase):
    purchaseID: int = Field(..., description="ID of the purchase")
    createdBy: int = Field(..., description="ID of the user who created the status")
    createdAt: dt = Field(default_factory=dt.now, description="Creation timestamp")

class PurchaseStatusResponse(PurchaseStatusBase):
    id: int
    purchaseID: int
    createdAt: dt
    createdBy: int

    class Config:
        from_attributes = True

class PurchaseUpdateStatus(BaseModel):
    id: int = Field(..., description="ID of the purchase")
    isInvoiceAttached: bool = Field(..., description="Flag to indicate if the invoice is attached")
    isReceiptAttached: bool = Field(..., description="Flag to indicate if the receipt is attached")
    isTaxInvoiceAttached: bool = Field(..., description="Flag to indicate if the tax invoice is attached")
    isCopAttached: bool = Field(..., description="Flag to indicate if the COP is attached")
    isCopyPurchaseOrderAttached: bool = Field(..., description="Flag to indicate if the copy purchase order is attached")
    invoiceName: str = Field(..., description="Name of the invoice")
    receiptName: str = Field(..., description="Name of the receipt")
    taxInvoiceName: Optional[str] = Field(None, description="Name of the tax invoice")
    date: d = Field(..., description="Date of the purchase")
    dueDate: d = Field(..., description="Due date of the purchase")

class PurchaseCheckRequest(BaseModel):
    invoiceName: str = Field(..., description="Invoice name to check")
    purchaseOrderName: str = Field(..., description="Purchase order name to check")

class PurchaseFilter(BaseModel):
    isDue: bool = False
    isNotDue: bool = False
    isPaid: bool = False
    isUnpaid: bool = False
    isDraft: bool = False
    isReady: bool = False