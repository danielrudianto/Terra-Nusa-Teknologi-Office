from pydantic import BaseModel, Field
from typing import Optional, Annotated
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float
from utils.database import metadata
from datetime import date as d, datetime as dt
from utils.database import database
from sqlalchemy.exc import IntegrityError
from utils.logger_utils import log_error

# Define the Purchase model
class Asset(BaseModel):
    id: Optional[int] = Field(default=None, title="ID of the bank account", ge=1)
    name: Annotated[str, Field(max_length=45)] = Field(..., title="Name of the asset")
    description: Annotated[str, Field(max_length=500)] = Field(..., title="Description of the asset")
    brand: Annotated[str, Field(max_length=50)] = Field(..., title="Brand of the asset")
    type: Annotated[str, Field(max_length=50)] = Field(..., title="Type of the asset")
    depreciation: int = Field(..., title="Depreciation period in months", ge=0)
    location: Annotated[str, Field(max_length=50)] = Field(..., title="Location of the asset")
    purchaseOrderName: Annotated[str, Field(max_length=100)] = Field(..., title="Purchase order name")
    value: float = Field(..., title="Value of the asset", ge=0)
    createdBy: int | None = None  # ID of the user who created the bank account
    createdAt: Optional[dt] = None
    updatedBy: Optional[int] = Field(default=None, title="ID of the user who last updated the asset", ge=1)
    updatedAt: Optional[dt] = Field(default=None, title="Last update timestamp")
    purchaseDate: d = Field(..., title="Purchase date of the asset")
    soldValue: Optional[float] = Field(default=None, title="Sold value of the asset", ge=0)
    soldDate: Optional[float] = Field(default=None, title="Sold date of the asset")

    # Initialize the model with default values
    def __init__(self, **data):
        super().__init__(**data)
        if self.createdAt is None:
            self.createdAt = dt.now()

    async def create(self):
        """
        Create a new asset in the database.
        
        Returns:
            Dict: A success message with the created asset ID.
        """
        try:
            query = asset_table.insert().values(
                name=self.name,
                description=self.description,
                brand=self.brand,
                type=self.type,
                depreciation=self.depreciation,
                location=self.location,
                purchaseOrderName=self.purchaseOrderName,
                value=self.value,
                purchaseDate=self.purchaseDate,
                soldValue=None,
                soldDate=None,
                createdBy=self.createdBy,
                createdAt=self.createdAt,
            )
            result = await database.execute(query)
            return {"message": "Asset created successfully", "asset_id": result}
        except IntegrityError as e:
            # Handle integrity errors, such as unique constraint violations
            log_error(f"Integrity error while creating asset: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            # Handle any other exceptions
            log_error(f"Unexpected error while creating asset: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_assets(page: int, pageSize: int, keyword: str):
        query = asset_table.select().limit(pageSize).offset((page -1) * pageSize)
        try:
            result = await database.fetch_all(query) 
            response = []
            for row in result:
                response.append(
                    Asset(
                        id=row.id,
                        name=row.name,
                        description=row.description,
                        brand=row.brand,
                        type=row.type,
                        depreciation=row.depreciation,
                        location=row.location,
                        purchaseOrderName=row.purchaseOrderName,
                        purchaseDate=row.purchaseDate,
                        value=row.value,
                        createdBy=row.createdBy,
                        createdAt=row.createdAt,
                        updatedBy=row.updatedBy,
                        updatedAt=row.updatedAt,
                        soldValue=row.soldValue,
                        soldDate=row.soldDate
                    )
                )

            count_query = asset_table.select()
            count = await database.fetch_val(count_query)
            
            return {"data": response, "count": count if count is not None else 0}
        except Exception as e:
            log_error(f"Unexpected error while fetching assets: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

# Define the SQLAlchemy table
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
    