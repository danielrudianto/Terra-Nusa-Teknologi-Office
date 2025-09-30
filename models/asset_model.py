from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Annotated
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, select, func
from utils.database import metadata
from datetime import date as d, datetime as dt
from utils.database import database
from sqlalchemy.exc import IntegrityError
from utils.logger_utils import log_error

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

# Pydantic Models for different scenarios
class AssetBase(BaseModel):
    name: Annotated[str, Field(max_length=45)] = Field(..., title="Name of the asset")
    description: Annotated[str, Field(max_length=500)] = Field(..., title="Description of the asset")
    brand: Annotated[str, Field(max_length=50)] = Field(..., title="Brand of the asset")
    type: Annotated[str, Field(max_length=50)] = Field(..., title="Type of the asset")
    depreciation: int = Field(..., title="Depreciation period in months", ge=0)
    location: Annotated[str, Field(max_length=50)] = Field(..., title="Location of the asset")
    purchaseOrderName: Annotated[str, Field(max_length=100)] = Field(..., title="Purchase order name")
    value: float = Field(..., title="Value of the asset", ge=0)
    purchaseDate: d = Field(..., title="Purchase date of the asset")

class AssetCreate(AssetBase):
    createdBy: int | None = None

class AssetUpdate(BaseModel):
    name: Optional[Annotated[str, Field(max_length=45)]] = None
    description: Optional[Annotated[str, Field(max_length=500)]] = None
    brand: Optional[Annotated[str, Field(max_length=50)]] = None
    type: Optional[Annotated[str, Field(max_length=50)]] = None
    depreciation: Optional[int] = Field(None, ge=0)
    location: Optional[Annotated[str, Field(max_length=50)]] = None
    purchaseOrderName: Optional[Annotated[str, Field(max_length=100)]] = None
    value: Optional[float] = Field(None, ge=0)
    purchaseDate: Optional[d] = None
    soldValue: Optional[float] = Field(default=None, ge=0)
    soldDate: Optional[d] = None
    updatedBy: Optional[int] = Field(default=None, ge=1)

class AssetResponse(AssetBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., title="ID of the asset", ge=1)
    soldValue: Optional[float] = Field(default=None, title="Sold value of the asset", ge=0)
    soldDate: Optional[d] = Field(default=None, title="Sold date of the asset")
    createdBy: Optional[int] = None
    createdAt: Optional[dt] = None
    updatedBy: Optional[int] = Field(default=None, title="ID of the user who last updated the asset", ge=1)
    updatedAt: Optional[dt] = Field(default=None, title="Last update timestamp")