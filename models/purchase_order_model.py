from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, DECIMAL, JSON, Enum, ForeignKey
from utils.database import metadata
from datetime import datetime as dt
import enum

# Define enum for status
class PurchaseOrderStatus(enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    COMPLETED = "completed"

# Define the purchase_orders table
purchase_orders_table = Table(
    "purchase_orders",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date", Date, nullable=False),
    Column("supplierID", Integer, ForeignKey("suppliers.id"), nullable=False),
    Column("name", String(255), nullable=False),
    Column("purchaseType", String(50), nullable=False),
    Column("templateVersion", String(50), nullable=False),
    Column("projectName", String(255), nullable=False),
    Column("dpp", DECIMAL(15, 2), nullable=False),
    Column("status", Enum(PurchaseOrderStatus), default=PurchaseOrderStatus.DRAFT),
    Column("customData", JSON, default=None),
    Column("ppn", DECIMAL(5, 2), nullable=False, default=0.00),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("createdAt", DateTime, nullable=False, default=dt.now()),
    Column("isDelete", Boolean, default=False),
    Column("deletedBy", Integer, ForeignKey("users.id"), default=None),
    Column("deletedAt", DateTime, default=None),
)