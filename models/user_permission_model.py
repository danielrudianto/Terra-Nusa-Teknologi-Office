from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
)

from utils.database import metadata

"""
Izin khusus per pengguna.

Tabel ini hanya memuat PENGECUALIAN terhadap level bawaan. Pengguna yang
seluruh aksesnya mengikuti levelnya tidak punya baris di sini.
"""

user_permissions_table = Table(
    "user_permissions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("userID", Integer, ForeignKey("users.id"), nullable=False),
    Column("module", String(64), nullable=False),
    Column("action", String(16), nullable=False),
    # True  -> diizinkan meski level kurang
    # False -> dilarang meski level cukup
    Column("allowed", Boolean, nullable=False, default=True),
    Column("note", String(255), nullable=True),
    Column("createdBy", Integer, nullable=True),
    Column("createdAt", DateTime, nullable=False),
    Column("updatedBy", Integer, nullable=True),
    Column("updatedAt", DateTime, nullable=True),
    UniqueConstraint("userID", "module", "action", name="uq_user_module_action"),
)