from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, ForeignKey
from utils.database import metadata
from datetime import datetime

# Define the SQLAlchemy table
users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(100), nullable=False),
    Column("password", String(255)),
    Column("email", String(100), unique=True),
    # Jabatan, dicetak di bawah nama pada blok tanda tangan dokumen.
    #
    # Tidak diturunkan dari level akses: level menentukan APA yang boleh
    # dilakukan, bukan apa jabatannya. Seorang General Manager dan seorang
    # Direktur bisa sama-sama level 4, dan menebak dari level membuat dokumen
    # menyebut jabatan yang salah.
    Column("position", String(100), nullable=True),
    Column("isActive", Boolean, default=True),
    Column("isDeleted", Boolean, default=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("createdAt", DateTime(), nullable=False, default=datetime.now()),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("authenticationLevel", Integer, default=1, nullable=False, comment="Authentication level of the user, between 1 and 5"),
)