from datetime import datetime as dt
from sqlalchemy import Table, Column, Integer, Boolean, DateTime, Float, String
from utils.database import metadata

interpayment_table = Table(
    "interpayments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("bankAccountIDOrigin", Integer(), nullable=False),
    Column("bankAccountIDDestination", Integer(), nullable=False),
    Column("amount", Float(), nullable=False),
    # Panjang WAJIB disebut.
    #
    # `String` tanpa panjang tidak dapat disusun menjadi DDL MySQL, dan
    # `metadata.create_all` menolak SELURUH skema karenanya — bukan satu
    # tabel ini saja. Panjangnya disamakan dengan kolom `description` lain
    # (asset, expense, employee_form): 500.
    #
    # PERIKSA terhadap produksi sebelum dipakai membangun ulang: kolom yang
    # sudah ada di sana mungkin panjangnya berbeda, dan `cek_skema.py` hanya
    # membandingkan ADA/TIDAKNYA kolom, bukan tipenya.
    Column("description", String(500), nullable=False),
    Column("date", DateTime(), default=dt.now, nullable=False),
    Column("isDelete", Boolean(), default=False, nullable=False),
    Column("createdBy", Integer(), nullable=False),
    Column("createdAt", DateTime(), default=dt.now, nullable=False),
    Column("deletedBy", Integer(), nullable=True),
    Column("deletedAt", DateTime(), default=None, onupdate=dt.now, nullable=True)
)