from pydantic import BaseModel, Field
from typing import Optional, Annotated
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float
from utils.database import metadata
from datetime import date

# Define the Purchase model
class Purchase(BaseModel):
    invoiceName: str  # Name of the invoice
    receiptName: str  # Name of the receipt
    taxInvoiceName: str | None = None  # Name of the tax invoice
    supplierID: int  # ID of the supplier
    date: date  # Date of the purchase
    dueDate: date | None = None
    purchaseOrderName: str  # Name of the purchase order
    projectName: str  # Name of the project
    purchaseType: str  # Type of the purchase
    dpp: Annotated[float, Field(ge=0)]  # DPP value (greater than or equal to 0)
    ppn: Annotated[float, Field(ge=0)]  # PPN value (optional)
    pbbkb: Annotated[float, Field(ge=0)]  # PBBKB value (optional)
    pphCode: str  # PPH code
    pphTaxObject: str  # PPH tax object
    pphPercentage: Annotated[float, Field(ge=0, le=10)]  # PPH percentage (0-10%)
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

# Define the SQLAlchemy table
purchases_table = Table(
    "purchases",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("invoice_name", String(100), nullable=False),
    Column("receipt_name", String(100), nullable=False),
    Column("tax_invoice_name", String(100), nullable=True),
    Column("supplier_id", Integer, nullable=False),
    Column("date", Date(), nullable=False),
    Column("due_date", Date(), nullable=True),
    Column("purchase_order_name", String(100), nullable=False),
    Column("project_name", String(100), nullable=False),
    Column("purchase_type", String(100), nullable=False),
    Column("dpp", Float(), nullable=False),
    Column("ppn", Float(), nullable=False),
    Column("pbbkb", Float(), nullable=False),
    Column("pph_code", String(100), nullable=False),
    Column("pph_tax_object", String(100), nullable=False),
    Column("pph_percentage", Float(), nullable=False),
    Column("other_value", Float(), nullable=True),
    Column("other_value_note", String(255), nullable=True),
    Column("is_invoice_attached", Boolean(), nullable=False),
    Column("is_receipt_attached", Boolean(), nullable=False),
    Column("is_tax_invoice_attached", Boolean(), nullable=False),
    Column("is_cop_attached", Boolean(), nullable=False),
    Column("is_copy_purchase_order_attached", Boolean(), nullable=False),
    Column("bank_name", String(100), nullable=False),
    Column("bank_account_name", String(100), nullable=False),
    Column("bank_account_number", String(100), nullable=False),
    Column("payment_method", String(100), nullable=False),
    Column("is_paid", Boolean(), nullable=False, default=False),
    Column("is_delete", Boolean(), nullable=False, default=False),
    Column("created_at", DateTime(), nullable=False, default=date.today()),
    Column("updated_at", DateTime(), nullable=True, default=None),
    Column("deleted_at", DateTime(), nullable=True, default=None),
    Column("created_by", Integer, nullable=False),
    Column("updated_by", Integer, nullable=True),
    Column("deleted_by", Integer, nullable=True),
)