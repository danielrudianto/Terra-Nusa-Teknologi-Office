from sqlalchemy import (
    Table, Column, Integer, String, Text, DECIMAL, ForeignKey, text,
)
from utils.database import metadata

purchase_order_items_table = Table(
    "purchase_order_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("equipment_id", Integer, ForeignKey("master_item.id"), nullable=True),
    Column("fleet_id", Integer, nullable=True),  # references hardcoded frontend fleet list (no DB table)
    Column("task", String(100), nullable=True),
    Column("quantity", DECIMAL(12, 2), nullable=False, server_default="0.00"),
    Column("price", DECIMAL(12, 2), nullable=False, server_default="0.00"),
    Column("remarks_1", Text, nullable=True),
    Column("remarks_2", Text, nullable=True),
    Column("remarks_3", Text, nullable=True),
    Column("remarks_4", Text, nullable=True),
    Column("unit", String(45), nullable=False, server_default=""),
    Column("purchaseOrderID", Integer, ForeignKey("purchase_orders.id"), nullable=False),
)