from pydantic import BaseModel, Optional, Field
from typing import Annotated
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date
from utils.database import metadata
from datetime import date

# Define the Client model
class Purchase(BaseModel):
    purchase_date: date
    supplier_id: int
    project_id: int  # ID of the project
    created_by: int  # ID of the user who created the purchase
    created_at: date  # Date when the purchase was created
    is_delete: bool = False  # Flag to indicate if the purchase is deleted
    deleted_by: Optional[int] = None  # ID of the user who deleted the purchase (optional)
    deleted_at: Optional[date] = None  # Date when the purchase was deleted (optional)
    pph_rate: Annotated[float, Field(ge=0, le=10)]  # PPH rate (0-10%)
    dpp: Annotated[float, Field(ge=0)]  # DPP value (greater than or equal to 0)
    ppn: Optional[float] = None  # PPN value (optional)
    pbbkb: Optional[float] = None  # PBBKB value (optional)
    due_date: Optional[date] = None  # Due date for the purchase (optional)
    purchase_order_id: int # ID of the purchase order
    
# Define the SQLAlchemy table
purchases_table = Table(
    "purchases",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("purchase_date", Date()),
    Column("supplier_id", Integer),
    Column("project_id", Integer),
    Column("created_by", Integer),
    Column("created_at", DateTime()),
    Column("is_delete", Boolean, default=False),
    Column("pph_rate", float(), nullable=False, default=0),
    Column("dpp", float()),
    Column("ppn", float(), nullable=False, default=0),
    Column("pbbkb", float(), nullable=False, default=0),
    Column("due_date", DateTime(), nullable=False, default=0),
    Column("purchase_order_id", Integer)
)
    