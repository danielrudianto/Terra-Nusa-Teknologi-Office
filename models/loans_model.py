from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey
from utils.database import metadata
from datetime import datetime as dt

# Define the loans table
loans_table = Table(
    "loans",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date", Date, nullable=False),
    # Panjang WAJIB disebut — lihat catatan pada interpayments.description.
    # Disamakan dengan kolom nama lain: 100.
    Column("creditorName", String(100), nullable=False),
    # Alamat: 500, sama seperti kolom alamat lain.
    Column("creditorAddress", String(500), nullable=False),
    Column("creditorNPWP", String(22), default=None, nullable=True),
    Column("description", String(500), nullable=False, default=""),
    Column("received", Float, nullable=False, default=0),
    Column("debt", Float, nullable=False, default=0),
    Column("bankAccountName", String(100), nullable=False),
    Column("bankAccountNumber", String(100), nullable=False),
    Column("bankName", String(100), nullable=False),
    # rekening PERUSAHAAN tempat dana pinjaman diterima (beda dari rekening kreditur di atas)
    Column("bankAccountID", Integer, ForeignKey("bank_accounts.id"), nullable=True, default=None),
    Column("createdAt", DateTime(), nullable=False, default=dt.now()),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True, default=None),
    Column("isPaid", Boolean(), nullable=False, default=False),
)