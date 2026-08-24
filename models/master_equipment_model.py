from sqlalchemy import (
    Table, Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func, text,
)
from utils.database import metadata

# Catalogue of rentable heavy equipment (forklift, crane, excavator, genset, ...)
master_equipment_table = Table(
    "master_equipment",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False),
    Column("category", String(45), nullable=False),
    Column("capacity", String(45), nullable=True),
    Column("brand", String(45), nullable=True),
    Column("unit", String(45), nullable=False, server_default="hari"),
    Column("isDelete", Boolean, nullable=False, server_default=text("0"), default=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("createdAt", DateTime, server_default=func.now(), nullable=True),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("updatedAt", DateTime, nullable=True),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("deletedAt", DateTime, nullable=True),
)