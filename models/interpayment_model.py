from datetime import datetime as dt
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import Table, Column, Integer, Boolean, DateTime, Float, insert, select, func, and_, or_
from utils.database import metadata, database
from utils.logger_utils import log_error
from models.bank_model import bank_accounts_table

class Interpayment(BaseModel):
    id: Optional[int] = Field(default=None, title="ID of the bank account", ge=1)
    bankAccountIDOrigin: int = Field(..., title="ID of the origin bank account", ge=1)
    bankAccountIDDestination: int = Field(..., title="ID of the destination bank account", ge=1)
    amount: float = Field(..., title="Amount to be transferred", ge=0)
    date: dt = Field(default_factory=dt.now, title="Date of the interpayment")
    createdBy: int | None = Field(default=None, title="ID of the user who created the interpayment", ge=1)
    createdAt: dt = Field(default_factory=dt.now, title="Creation date of the interpayment")
    isDelete: bool = Field(default=False, title="Flag to indicate if the interpayment is deleted")
    deletedBy: int | None = Field(default=None, title="ID of the user who deleted the interpayment", ge=1)
    deletedAt: dt | None = Field(default=None, title="Deletion date of the interpayment")

    @staticmethod
    async def create_interpayment(interpayment_data: dict):
        """
        Create an interpayment in the database.
        """
        try:
            if not interpayment_data:
                return {"message": "No interpayment data to create."}
            query = insert(interpayment_table).values(interpayment_data)
            result = await database.execute(query)
            if not result:
                return {"error": "Failed to create interpayment", "status": 500}
            
            return {"message": "Interpayment created successfully", "interpaymentID": result}
        except Exception as e:
            log_error(f"Error creating interpayment: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_interpayments(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str):
        """
        Retrieve a list of interpayments from the database.
        """
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        # #Bank account table
        origin_bank_alias = bank_accounts_table.alias("origin_bank")
        destination_bank_alias = bank_accounts_table.alias("destination_bank")

        select_columns = [
            interpayment_table,  # Selects all columns from interpayment_table
            origin_bank_alias.c.bankName.label("originBankName"),
            origin_bank_alias.c.bankAccountName.label("originBankAccountName"),
            origin_bank_alias.c.bankAccountNumber.label("originBankAccountNumber"),
            destination_bank_alias.c.bankName.label("destinationBankName"),
            destination_bank_alias.c.bankAccountName.label("destinationBankAccountName"),
            destination_bank_alias.c.bankAccountNumber.label("destinationBankAccountNumber"),
        ]

        conditions = [interpayment_table.c.isDelete == False]
        
        try:
            offset = (page - 1) * pageSize
            query = (
                select(*select_columns)
                .join(
                    origin_bank_alias,
                    interpayment_table.c.bankAccountIDOrigin == origin_bank_alias.c.id,
                    isouter=True  # Use LEFT OUTER JOIN if origin bank might not exist (though FK implies it should)
                )
                .join(
                    destination_bank_alias,
                    interpayment_table.c.bankAccountIDDestination == destination_bank_alias.c.id,
                    isouter=True  # Use LEFT OUTER JOIN for destination bank as well
                )
                .where(and_(*conditions)) # Use and_() to combine conditions
                .offset(offset)
                .limit(pageSize)
                .order_by(getattr(interpayment_table.c, sortBy).desc() if sortByDirection == "desc" else getattr(interpayment_table.c, sortBy))
            )
            result = await database.fetch_all(query)

            # Now count it
            count_query = select(func.count()).select_from(interpayment_table).where(interpayment_table.c.isDelete == False)
            total_count = await database.fetch_val(count_query)
            
            return {
                "data": [dict(row) for row in result],
                "count": total_count,
            }
        except Exception as e:
            log_error(f"Error fetching interpayments: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_interpayment_calendar_data(month: int, year: int, bankAccountID: list[int]):
        """
        Retrieve a list of interpayments from the database.
        """
        #Bank account table
        origin_bank_alias = bank_accounts_table.alias("origin_bank")
        destination_bank_alias = bank_accounts_table.alias("destination_bank")

        select_columns = [
            interpayment_table,  # Selects all columns from interpayment_table
            origin_bank_alias.c.bankName.label("originBankName"),
            origin_bank_alias.c.bankAccountName.label("originBankAccountName"),
            origin_bank_alias.c.bankAccountNumber.label("originBankAccountNumber"),
            destination_bank_alias.c.bankName.label("destinationBankName"),
            destination_bank_alias.c.bankAccountName.label("destinationBankAccountName"),
            destination_bank_alias.c.bankAccountNumber.label("destinationBankAccountNumber"),
        ]

        conditions = [
            interpayment_table.c.isDelete == False, 
            func.extract('month', interpayment_table.c.date) == month,
            func.extract('year', interpayment_table.c.date) == year,
        ]
        
        try:
            query = (
                select(*select_columns)
                .join(
                    origin_bank_alias,
                    interpayment_table.c.bankAccountIDOrigin == origin_bank_alias.c.id,
                    isouter=True  # Use LEFT OUTER JOIN if origin bank might not exist (though FK implies it should)
                )
                .join(
                    destination_bank_alias,
                    interpayment_table.c.bankAccountIDDestination == destination_bank_alias.c.id,
                    isouter=True  # Use LEFT OUTER JOIN for destination bank as well
                )
                .where(and_(*conditions)) # Use and_() to combine conditions
            )
            result = await database.fetch_all(query)

            return [dict(row) for row in result]
        except Exception as e:
            log_error(f"Error fetching interpayments: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_interpayment_calendar_data_by_date(date: int, month: int, year: int, bankAccountID: list[int] | None):
        """
        Retrieve a list of interpayments from the database.
        """
        #Bank account table
        origin_bank_alias = bank_accounts_table.alias("origin_bank")
        destination_bank_alias = bank_accounts_table.alias("destination_bank")

        select_columns = [
            interpayment_table,  # Selects all columns from interpayment_table
            origin_bank_alias.c.bankName.label("originBankName"),
            origin_bank_alias.c.bankAccountName.label("originBankAccountName"),
            origin_bank_alias.c.bankAccountNumber.label("originBankAccountNumber"),
            destination_bank_alias.c.bankName.label("destinationBankName"),
            destination_bank_alias.c.bankAccountName.label("destinationBankAccountName"),
            destination_bank_alias.c.bankAccountNumber.label("destinationBankAccountNumber"),
        ]

        conditions = [
            interpayment_table.c.isDelete == False, 
            func.extract('day', interpayment_table.c.date) == date,
            func.extract('month', interpayment_table.c.date) == month,
            func.extract('year', interpayment_table.c.date) == year,
        ]
        
        if bankAccountID is not None:
            conditions.append(
                or_(
                    interpayment_table.c.bankAccountIDOrigin.in_(bankAccountID),
                    interpayment_table.c.bankAccountIDDestination.in_(bankAccountID)
                )
            )
        
        try:
            query = (
                select(*select_columns)
                .join(
                    origin_bank_alias,
                    interpayment_table.c.bankAccountIDOrigin == origin_bank_alias.c.id,
                    isouter=True  # Use LEFT OUTER JOIN if origin bank might not exist (though FK implies it should)
                )
                .join(
                    destination_bank_alias,
                    interpayment_table.c.bankAccountIDDestination == destination_bank_alias.c.id,
                    isouter=True  # Use LEFT OUTER JOIN for destination bank as well
                )
                .where(and_(*conditions)) # Use and_() to combine conditions
            )
            result = await database.fetch_all(query)

            return [dict(row) for row in result]
        except Exception as e:
            log_error(f"Error fetching interpayments: {str(e)}")
            return {"error": str(e), "status": 500}
        
interpayment_table = Table(
    "interpayments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("bankAccountIDOrigin", Integer(), nullable=False),
    Column("bankAccountIDDestination", Integer(), nullable=False),
    Column("amount", Float(), nullable=False),
    Column("date", DateTime(), default=dt.now, nullable=False),
    Column("isDelete", Boolean(), default=False, nullable=False),
    Column("createdBy", Integer(), nullable=False),
    Column("createdAt", DateTime(), default=dt.now, nullable=False),
    Column("deletedBy", Integer(), nullable=True),
    Column("deletedAt", DateTime(), default=None, onupdate=dt.now, nullable=True)
)