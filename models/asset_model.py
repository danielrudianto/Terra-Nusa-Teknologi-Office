from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float
from utils.database import metadata
from datetime import datetime as dt

# SQLAlchemy Table Definition
asset_table = Table(
    "assets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(45), nullable=False),
    Column("description", String(500), nullable=False),
    Column("brand", String(50), nullable=False),
    Column("type", String(50), nullable=False),
    Column("depreciation", Integer(), nullable=False),
    Column("location", String(50), nullable=False),
    Column("purchaseOrderName", String(100), nullable=False),
    Column("purchaseDate", Date(), nullable=False),
    Column("value", Float(), nullable=False),
    Column("createdBy", Integer(), nullable=False),
    Column("createdAt", DateTime(), default=dt.now, nullable=False),
    Column("updatedBy", Integer(), nullable=True),
    Column("updatedAt", DateTime(), default=None, onupdate=dt.now, nullable=True),
    Column("soldValue", Float, nullable=True),
    Column("soldDate", Date(), nullable=True)
)

# This file should ONLY contain the SQLAlchemy table definition
# No classes or methods that import from other modules