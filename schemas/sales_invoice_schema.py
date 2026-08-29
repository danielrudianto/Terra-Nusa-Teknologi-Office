from pydantic import BaseModel, ConfigDict
from datetime import datetime as dt, date as d
from typing import Optional

class SalesInvoiceBase(BaseModel):
    name: str
    date: d
    projectName: str
    clientID: int
    dpp: float
    pphCode: Optional[str] = None
    pphTaxObject: Optional[str] = None
    pphPercentage: float
    ppn: float
    bpjs: float
    spkNumber: str
    description: str
    bankAccountID: int
    # Faktur dicetak terpisah dari lampirannya.
    #
    # Layar pembuatannya sudah lama punya isian ini dan kolomnya sudah ada di
    # basis data, tetapi tidak pernah sampai ke sini — pilihan penggunanya
    # hilang tanpa galat apa pun.
    separatedInvoice: bool = False
    # Masa pajak faktur keluaran; NULL/None berarti ikut `date`.
    taxPeriod: Optional[d] = None
    isApprove: bool = False
    isDelete: bool = False

class SalesInvoiceCreate(SalesInvoiceBase):
    createdBy: Optional[int] = None

class SalesInvoiceUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[d] = None
    projectName: Optional[str] = None
    clientID: Optional[int] = None
    dpp: Optional[float] = None
    pphCode: Optional[str] = None
    pphTaxObject: Optional[str] = None
    pphPercentage: Optional[float] = None
    ppn: Optional[float] = None
    bpjs: Optional[float] = None
    spkNumber: Optional[str] = None
    description: Optional[str] = None
    bankAccountID: Optional[int] = None
    taxInvoiceName: Optional[str] = None
    taxPeriod: Optional[d] = None
    incomeTaxInvoiceName: Optional[str] = None
    separatedInvoice: Optional[bool] = None
    isApprove: bool = False
    isDelete: bool = False
    updatedBy: Optional[int] = None

class SalesInvoiceResponse(SalesInvoiceBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    taxInvoiceName: Optional[str] = None
    createdBy: Optional[int] = None
    createdAt: Optional[dt] = None
    isApprove: bool = False
    isDelete: bool = False
    updatedBy: Optional[int] = None
    updatedAt: Optional[dt] = None

class SalesInvoiceWithClientResponse(SalesInvoiceResponse):
    client_name: Optional[str] = None
    client_id: Optional[int] = None
    client_address: Optional[str] = None
    client_city: Optional[str] = None
    client_province: Optional[str] = None
    client_prefix: Optional[str] = None

class SalesInvoiceWithPaymentsResponse(SalesInvoiceWithClientResponse):
    payments: list = []


class SalesInvoiceTaxInvoiceUpdate(BaseModel):
    """
    Set nomor faktur pajak PPN, beserta masa pajaknya.

    `taxPeriod` opsional dan boleh dikosongkan: kosong berarti fakturnya
    dilaporkan pada masa tanggal invoicenya sendiri — keadaan yang normal.
    Diisi hanya bila fakturnya jatuh ke masa yang berbeda.
    """
    taxInvoiceName: str
    taxPeriod: Optional[d] = None


class SalesInvoiceIncomeTaxUpdate(BaseModel):
    """Set nomor bukti potong PPh."""
    incomeTaxInvoiceName: str