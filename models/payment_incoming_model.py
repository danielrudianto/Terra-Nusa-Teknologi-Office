from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey
from utils.database import metadata
from datetime import datetime as dt

# Define the payment_incoming table
payment_incoming_table = Table(
    "payment_incoming",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date", Date(), nullable=False),
    Column("amount", Integer, nullable=False),
    Column("salesInvoiceID", Integer, ForeignKey("purchases.id"), nullable=True),
    Column("incomeID", Integer, ForeignKey('income.id'), nullable=True),
    Column("loanID", Integer, ForeignKey('loans.id'), nullable=True),
    Column("bankAccountID", Integer, ForeignKey("bank_accounts.id"), nullable=True),
    Column("createdAt", DateTime(), nullable=False, default=dt.now()),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True, default=None),
    Column("isDelete", Boolean, default=False),
    Column("isApprove", Boolean, default=False),
    # Kolom hapus lunak melengkapi `isDelete`.
    #
    # Keduanya sudah ada di basis data tetapi tidak pernah didaftarkan di
    # model, sehingga jejak SIAPA dan KAPAN menghapus pembayaran masuk tidak
    # dapat dibaca maupun ditulis lewat aplikasi.
    Column('deletedAt', DateTime(), nullable=True, default=None),
    Column('deletedBy', Integer, ForeignKey('users.id'), nullable=True, default=None),
)