from utils.database import metadata
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey

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
    Column("procurementType", String(100), nullable=False, default="goods"),
    # DECIMAL(17,4) di basis data, bukan FLOAT — `Float()` di sini warisan
    # dan sengaja dibiarkan: menggantinya membuat `databases` mengembalikan
    # `Decimal`, dan `float * Decimal` melempar TypeError di repository.
    Column("dpp", Float(), nullable=False),
    # DECIMAL(12,2). Tarif, tetap dua desimal.
    Column("ppn", Float(), nullable=False),
    # DECIMAL(17,4).
    Column("pbbkb", Float(), nullable=False),
    Column("pphCode", String(100), nullable=True),
    Column("pphTaxObject", String(500), nullable=True),
    Column("pphPercentage", Float(), nullable=False),
    # DECIMAL(14,4).
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
    Column("createdAt", DateTime(), nullable=False),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("lastStatus", String(100), nullable=False, default="draft"),
    Column("lastStatusDescription", String(100), nullable=True, default=None),
    Column("isInternal", Boolean(), nullable=False, default=False)
)

purchase_status_table = Table(
    "purchase_status",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("purchaseID", Integer, nullable=False),
    Column("status", String(100), nullable=False),
    Column("createdBy", Integer, nullable=False),
    Column("createdAt", DateTime(), nullable=False),
    Column("description", String(255), nullable=True),
)