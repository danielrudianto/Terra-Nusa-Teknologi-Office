from pydantic import BaseModel, Field
from typing import Optional, Annotated
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey
from utils.database import metadata
from datetime import date as d
from datetime import datetime as dt

# Define the Purchase model
class Purchase(BaseModel):
    invoiceName: str  # Name of the invoice
    receiptName: str  # Name of the receipt
    taxInvoiceName: str | None = None  # Name of the tax invoice
    supplierID: int  # ID of the supplier
    date: d  # Date of the purchase
    dueDate: d | None = None
    purchaseOrderName: str  # Name of the purchase order
    projectName: str  # Name of the project
    purchaseType: str  # Type of the purchase
    dpp: Annotated[float, Field(ge=0)]  # DPP value (greater than or equal to 0)
    ppn: Annotated[float, Field(ge=0)]  # PPN value (optional)
    pbbkb: Annotated[float, Field(ge=0)]  # PBBKB value (optional)
    pphCode: str | None  # PPH code
    pphTaxObject: str | None  # PPH tax object
    pphPercentage: Annotated[float, Field(ge=0, le=16)]  # PPH percentage (0-10%)
    otherValue: Optional[float] = None  # Other value (optional)
    otherValueNote: Optional[str] = None  # Note for other value (optional)
    isInvoiceAttached: bool  # Flag to indicate if the invoice is attached
    isReceiptAttached: bool  # Flag to indicate if the receipt is attached
    isTaxInvoiceAttached: bool  # Flag to indicate if the tax invoice is attached
    isCopAttached: bool  # Flag to indicate if the COP is attached
    isCopyPurchaseOrderAttached: bool  # Flag to indicate if the copy purchase order is attached
    bankName: str  # Name of the bank
    bankAccountName: str  # Name of the bank account
    bankAccountNumber: str  # Bank account number
    paymentMethod: str  # Payment method
    isPaid: bool = False  # Flag to indicate if the purchase is paid
    isDelete: bool = False  # Flag to indicate if the purchase is deleted
    lastStatus: str  # Last status of the purchase
    lastStatusDescription: str | None

class PurchaseStatus(BaseModel):
    id: int  # ID of the purchase
    status: str  # Status of the purchase
    createdAt: dt  # Creation date of the purchase
    description: str  # Description of the status

class PurchaseUpdateStatus(BaseModel):
    id: int  # ID of the purchase
    isInvoiceAttached: bool  # Flag to indicate if the invoice is attached
    isReceiptAttached: bool  # Flag to indicate if the receipt is attached
    isTaxInvoiceAttached: bool  # Flag to indicate if the tax invoice is attached
    isCopAttached: bool  # Flag to indicate if the COP is attached
    isCopyPurchaseOrderAttached: bool  # Flag to indicate if the copy purchase order is attached    
    invoiceName: str  # Name of the invoice
    receiptName: str  # Name of the receipt
    taxInvoiceName: str | None  # Name of the tax invoice
    date: d  # Date of the purchase
    dueDate: d  # Due date of the purchase

# Define the SQLAlchemy table
purchases_table = Table(
    "purchases",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("invoiceName", String(100), nullable=False),
    Column("receiptName", String(100), nullable=False),
    Column("taxInvoiceName", String(100), nullable=True),
    Column("supplierID", Integer, nullable=False),
    Column("date", Date(), nullable=False),
    Column("dueDate", Date(), nullable=True),
    Column("purchaseOrderName", String(100), nullable=False),
    Column("projectName", String(100), nullable=False),
    Column("purchaseType", String(100), nullable=False),
    Column("dpp", Float(), nullable=False),
    Column("ppn", Float(), nullable=False),
    Column("pbbkb", Float(), nullable=False),
    Column("pphCode", String(100), nullable=True),
    Column("pphTaxObject", String(500), nullable=True),
    Column("pphPercentage", Float(), nullable=False),
    Column("otherValue", Float(), nullable=True),
    Column("otherValueNote", String(255), nullable=True),
    Column("isInvoiceAttached", Boolean(), nullable=False),
    Column("isReceiptAttached", Boolean(), nullable=False),
    Column("isTaxInvoiceAttached", Boolean(), nullable=False),
    Column("isCopAttached", Boolean(), nullable=False),
    Column("isCopyPurchaseOrderAttached", Boolean(), nullable=False),
    Column("bankName", String(100), nullable=False),
    Column("bankAccountName", String(100), nullable=False),
    Column("bankAccountNumber", String(100), nullable=False),
    Column("paymentMethod", String(100), nullable=False),
    Column("isPaid", Boolean(), nullable=False, default=False),
    Column("isDelete", Boolean(), nullable=False, default=False),
    Column("createdAt", DateTime(), nullable=False, default=dt.now()),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("lastStatus", String(100), nullable=False, default="Waiting"),
)

# Define the PurchaseStatus SQLAlchemy table
purchase_status_table = Table(
    "purchase_status",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("purchaseID", Integer, nullable=False),
    Column("status", String(100), nullable=False),
    Column("createdBy", Integer, nullable=False),
    Column("createdAt", DateTime(), nullable=False, default=dt.now()),
    Column("description", String(255), nullable=True),
)