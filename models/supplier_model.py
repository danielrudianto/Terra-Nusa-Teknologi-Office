from pydantic import BaseModel, EmailStr, StringConstraints, field_validator
from typing import Annotated
from sqlalchemy import ForeignKey, Table, Column, Integer, String, Boolean, insert, select, update
from utils.database import metadata
from utils.logger_utils import log_error
from utils.database import database
from datetime import datetime as dt
from sqlalchemy.exc import IntegrityError

# Define the Client model
class Supplier(BaseModel):
    id: int | None = None  # Unique ID for the supplier, optional for creation
    prefix: Annotated[str, StringConstraints(min_length=1, max_length=25)] | None = None  # Optional prefix, max length 25
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]  # Name must be between 1 and 100 characters
    address: Annotated[str, StringConstraints(min_length=1, max_length=255)]  # Address must be between 1 and 255 characters
    city: Annotated[str, StringConstraints(min_length=1, max_length=100)]  # City must be between 1 and 100 characters
    province: Annotated[str, StringConstraints(min_length=1, max_length=100)]  # Province must be between 1 and 100 characters
    phoneNumber: Annotated[str, StringConstraints(pattern=r"^[0-9]{10,20}$")]  # Phone number must be 10-15 digits, optional "+" at the start
    email: Annotated[EmailStr, StringConstraints(max_length=255)] | None = None  #Nullable string, must be a valid email format
    npwp: Annotated[str, StringConstraints(pattern=r"^\d{16}$")] | None = None  # Optional NPWP, must be 16 digits
    itemsSold: Annotated[str, StringConstraints(min_length=1, max_length=255)]  # Items sold must be between 1 and 255 characters
    serviceArea: Annotated[str, StringConstraints(min_length=1, max_length=255)]  # Service area must be between 1 and 255 characters
    createdBy: int | None = None  # ID of the user who created the supplier
    createdAt: dt | None = None  # Creation timestamp, should be in ISO format
    updatedBy: int | None = None  # ID of the user who last updated the supplier, optional
    updatedAt: dt | None = None  # Last update timestamp, optional
    deletedAt: dt | None = None  # Deletion timestamp, optional
    deletedBy: int | None = None  # ID of the user who deleted the supplier, optional
    isDelete: bool = False  # Default to True

    #Initialize the model
    def __init__(self, **data):
        super().__init__(**data)
        if not self.createdAt:
            self.createdAt = dt.now().isoformat()
        if not self.updatedAt:
            self.updatedAt = None
        if not self.deletedAt:
            self.deletedAt = None
        if not self.isDelete:
            self.isDelete = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str):
        """
        Validate the name field to ensure it is not empty.
        """
        if not value.strip():
            raise ValueError("Name cannot be empty.")
        return value
    
    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str):
        """
        Validate the address field to ensure it is not empty.
        """
        if not value.strip():
            raise ValueError("Address cannot be empty.")
        return value
    
    @field_validator("city")
    @classmethod
    def validate_city(cls, value: str):
        """
        Validate the city field to ensure it is not empty.
        """
        if not value.strip():
            raise ValueError("City cannot be empty.")
        return value
    
    @field_validator("province")
    @classmethod
    def validate_province(cls, value: str):
        """
        Validate the province field to ensure it is not empty.
        """
        if not value.strip():
            raise ValueError("Province cannot be empty.")
        return value
    
    @field_validator("phoneNumber")
    @classmethod
    def validate_phone_number(cls, value: str):
        """
        Validate the phone number field to ensure it matches the pattern.
        """
        if not value or not value.strip():
            raise ValueError("Phone number cannot be empty.")
        if not value.isdigit() or len(value) < 10 or len(value) > 20:
            raise ValueError("Phone number must be between 10 and 20 digits.")
        return value
    
    @field_validator("prefix")
    @classmethod
    def validate_prefix(cls, value: str | None):
        """
        Validate the prefix field to ensure it is not empty.
        """
        if value and not value.strip():
            raise ValueError("Prefix cannot be empty.")
        if value in ("CV.", "PT.", "UD.", "Yayasan", "Lainnya"):
            return value.strip()
        elif value is None:
            return None
        return value

    async def create(self) -> dict:
        """
        Create a new supplier in the database.
        """
        query = insert(suppliers_table).values(
            prefix=self.prefix,
            name=self.name,
            address=self.address,
            city=self.city,
            province=self.province,
            phoneNumber=self.phoneNumber,
            email=self.email,
            npwp=self.npwp,
            itemsSold=self.itemsSold,
            serviceArea=self.serviceArea,
            createdBy=self.createdBy,
            createdAt=self.createdAt,
            updatedBy=self.updatedBy,
            updatedAt=self.updatedAt,
            deletedAt=self.deletedAt,
            deletedBy=self.deletedBy,
            isDelete=self.isDelete,
        )

        try:
            supplierID = await database.execute(query)
            return {"message": "Supplier created successfully", "supplier_id": supplierID}
        except IntegrityError as e:
            log_error(f"Integrity error while creating supplier: {str(e)}")
            return {"error": "Something wrong with your input.", "status": 400}
        except Exception as e:
            log_error(f"Error creating supplier: {str(e)}")
            return {"error": str(e), "status": 500}

    async def update(self) -> dict:
        if not self.id:
            return {"error": "Supplier ID is required for update", "status": 400}
        query = (
            update(suppliers_table)
            .where(suppliers_table.c.id == self.id)
            .values(
                prefix=self.prefix,
                name=self.name,
                address=self.address,
                city=self.city,
                province=self.province,
                phoneNumber=self.phoneNumber,
                email=self.email,
                npwp=self.npwp,
                itemsSold=self.itemsSold,
                serviceArea=self.serviceArea,
                updatedBy=self.updatedBy,
                updatedAt=dt.now().isoformat(),
            )
        )

        try:
            await database.execute(query)
            return {"message": "Supplier updated successfully", "supplier_id": self.id}
        except IntegrityError as e:
            log_error(f"Integrity error while updating supplier: {str(e)}")
            return {"error": "Something wrong with your input.", "status": 400}
        except Exception as e:
            log_error(f"Error updating supplier: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_id(supplier_id: int) -> dict:
        """
        Get a supplier by ID from the database.
        """
        query = select(suppliers_table).where(suppliers_table.c.id == supplier_id)
        try:
            result = await database.fetch_one(query)
            if not result:
                return {"error": "Supplier not found", "status": 404}
            return dict(result)
        except Exception as e:
            log_error(f"Error fetching supplier by ID: {str(e)}")
            return {"error": str(e), "status": 500}

# Define the clients table
suppliers_table = Table(
    "suppliers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("prefix" , String(25), nullable=True),
    Column("name", String(255), nullable=False),
    Column("address", String(255), nullable=False),
    Column("city", String(100), nullable=False),
    Column("province", String(100), nullable=False),
    Column("phoneNumber", String(20), nullable=False),
    Column("email", String(255), nullable=True),
    Column("npwp", String(16), nullable=True),
    Column("itemsSold", String(1000), nullable=False),
    Column("serviceArea", String(1000), nullable=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("createdAt", String(50), nullable=False),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("updatedAt", String(50), nullable=True),
    Column("deletedAt", String(50), nullable=True),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("isDelete", Boolean, default=False, nullable=False, server_default="0"),
)