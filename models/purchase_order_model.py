from pydantic import BaseModel, Field
from typing import Annotated, Optional
from datetime import date
from sqlalchemy import Table, Column, Integer, String, Boolean, Float, DateTime
from utils.database import metadata

class PurchaseOrder(BaseModel):
    id: int  # Unique ID for the purchase order
    supplier_id: int  # ID of the supplier
    project_id: int  # ID of the project
    created_by: int  # ID of the user who created the order
    created_at: date  # Date when the order was created
    is_deleted: bool = False  # Flag to indicate if the order is deleted
    deleted_at: Optional[date] = None  # Date when the order was deleted (optional)
    deleted_by: Optional[int] = None  # ID of the user who deleted the order (optional)
    pph_rate: Annotated[float, Field(ge=0, le=10)]  # PPH rate (0-10%)
    ppn: Optional[float] = None  # PPN value (optional)
    
class PurchaseOrderItem(BaseModel):
    id: int  # Unique ID for the purchase order item
    purchase_order_id: int  # ID of the purchase order
    item_id: int  # ID of the item
    quantity: Annotated[float, Field(ge=0)]  # Quantity of the item (greater than or equal to 0)
    unit_price: Annotated[float, Field(ge=0)]  # Unit price of the item (greater than or equal to 0)
    
purchase_orders_table = Table(
    "purchase_orders",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("supplier_id", Integer),
    Column("project_id", Integer),
    Column("created_by", Integer),
    Column("created_at", DateTime()),
    Column("is_deleted", Boolean, default=False),
    Column("deleted_at", DateTime(), nullable=True),
    Column("deleted_by", Integer, nullable=True),
    Column("pph_rate", Float),
    Column("ppn", Float, nullable=True)
)

purchase_order_items_table = Table(
    "purchase_order_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("purchase_order_id", Integer),
    Column("item_id", Integer),
    Column("quantity", Float),
    Column("unit_price", Float)
)