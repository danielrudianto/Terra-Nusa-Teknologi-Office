from sqlalchemy import (
    ForeignKey,
    Table,
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    func,
    text,
)
from utils.database import metadata

# Master item catalog (goods staff pick from when creating purchase orders)
master_item_table = Table(
    "master_item",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("sku", String(45), nullable=False, unique=True),
    Column("description", Text, nullable=False),
    Column("brand", String(45), nullable=False),
    Column("type", String(45), nullable=False),
    Column("unit", String(45), nullable=False),
    Column("isDelete", Boolean, nullable=False, server_default=text("0"), default=False),
    # Barang yang sering dipakai, didahulukan pada PEMILIH barang.
    #
    # Katalognya seribu baris lebih; yang benar-benar dipakai sehari-hari
    # jauh lebih sedikit. Tanpa penanda ini, barang yang sama dicari ulang
    # setiap kali dan yang tidak menemukannya membuat entri kembar.
    #
    # Hanya memengaruhi urutan pada pemilih. Daftar Master Barang tetap urut
    # sesuai kolom yang dipilih penggunanya — di sana yang dicari justru
    # barang yang jarang dipakai.
    Column("isFavorite", Boolean, nullable=False, server_default="0", default=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("createdAt", DateTime, server_default=func.now(), nullable=True),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("updatedAt", DateTime, nullable=True),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("deletedAt", DateTime, nullable=True),
    Column("availablePurchaseType", String(100), nullable=True),
)