from sqlalchemy import Table, Column, Integer, ForeignKey, Float, Date, String, Boolean, DateTime
from utils.database import metadata
from datetime import datetime as dt

sales_invoice_tables = Table(
    "sales_invoices",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False),
    Column("date", Date, nullable=False),
    Column("projectName", String(10), nullable=False),
    Column("clientID", Integer, ForeignKey("clients.id"), nullable=False),
    Column("dpp", Float, nullable=False, default=0.0),
    Column("pphCode", String(100), nullable=True),
    Column("pphTaxObject", String(500), nullable=True),
    Column("pphPercentage", Float, nullable=False, default=0.0),
    Column("ppn", Float, nullable=False, default=0.0),
    Column("bpjs", Float, nullable=False, default=0.0),
    Column("spkNumber", String(100), nullable=False),
    Column("taxInvoiceName", String(100), nullable=True, default=None),
    Column("incomeTaxInvoiceName", String(100), nullable=True, default=None),
    Column("description", String(100), nullable=True),
    # Faktur dicetak terpisah dari lampirannya.
    #
    # Kolomnya sudah ada di basis data dan layar pembuatannya sudah punya
    # isian untuk ini, tetapi tidak pernah didaftarkan di model — sehingga
    # pilihan penggunanya tidak pernah tersimpan, dan tidak ada galat yang
    # muncul karenanya.
    Column('separatedInvoice', Boolean, nullable=True, default=False),
    Column("bankAccountID", Integer, ForeignKey("bank_accounts.id"), nullable=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False, default=1),
    Column("createdAt", Date, nullable=False, default=dt.utcnow().date()),
    Column("isApprove", Boolean, nullable=False, default=False),
    Column("isDelete", Boolean, nullable=False, default=False),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("updatedAt", DateTime, nullable=True, default=None)
)