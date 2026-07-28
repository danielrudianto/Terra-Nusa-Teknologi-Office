from sqlalchemy import ForeignKey, Table, Column, Integer, String, Boolean, text
from utils.database import metadata

# Define the suppliers table
suppliers_table = Table(
    "suppliers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("prefix" , String(25), nullable=True),
    Column("name", String(255), nullable=False),
    Column("address", String(255), nullable=False),
    Column("city", String(100), nullable=False),
    Column("province", String(100), nullable=False),
    Column("phoneNumber", String(20), nullable=False),
    Column("email", String(255), nullable=True),
    Column("npwp", String(16), nullable=True),
    Column("itemsSold", String(1000), nullable=False),
    Column("serviceArea", String(1000), nullable=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("createdAt", String(50), nullable=False),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("updatedAt", String(50), nullable=True),
    Column("deletedAt", String(50), nullable=True),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("isDelete", Boolean, default=False, nullable=False, server_default="false"),
    # --- blacklist (warns on purchase/PO, does not block) ---
    Column("isBlacklist", Boolean, default=False, nullable=False, server_default=text("0")),
    Column("blacklistReason", String(500), nullable=True),
    Column("blacklistedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("blacklistedAt", String(50), nullable=True),
)