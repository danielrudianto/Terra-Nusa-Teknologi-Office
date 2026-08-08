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
    incomeTaxInvoiceName: Optional[str] = None
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
    """Set nomor faktur pajak PPN."""
    taxInvoiceName: str


class SalesInvoiceIncomeTaxUpdate(BaseModel):
    """Set nomor bukti potong PPh."""
    incomeTaxInvoiceName: str