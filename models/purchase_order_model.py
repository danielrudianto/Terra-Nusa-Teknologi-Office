from sqlalchemy import (
    text,
    func,
    Table,
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Date,
    DECIMAL,
    JSON,
    Text,
    Enum,
    ForeignKey,
    Index,
)
from utils.database import metadata
from datetime import datetime as dt
import enum


# Status enum — matches the DB enum('draft','approved','completed','cancelled')
class PurchaseOrderStatus(enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Define the purchase_orders table (aligned to production DDL)
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
    Column(
        "status",
        Enum(
            "draft",
            "approved",
            "completed",
            "cancelled",
            name="purchase_order_status",
        ),
        server_default="draft",
        default="draft",
    ),
    Column("customData", JSON, nullable=True, default=None),
    Column("ppn", DECIMAL(5, 2), nullable=False, server_default="0.00", default=0.00),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("createdAt", DateTime, nullable=False, server_default=func.now(), default=dt.now),
    Column("isDelete", Boolean, server_default=text("0"), default=False),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True, default=None),
    Column("deletedAt", DateTime, nullable=True, default=None),
    Column("note", Text, nullable=True),
    Column("billing_requirements", JSON, nullable=False),
    Column("payment_term", String(45), nullable=False, server_default="CASH", default="CASH"),
    Column("revision", Integer, nullable=False, server_default="0", default=0),
    Column("isApproved", Boolean, nullable=False, server_default=text("0"), default=False),
    Column("approvedBy", Integer, ForeignKey("users.id"), nullable=True, default=None),
    Column("approvedAt", DateTime, nullable=True, default=None),
    Index("idx_supplier_date", "supplierID", "date"),
    Index("idx_type_status", "purchaseType", "status"),
)