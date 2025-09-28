from pydantic import BaseModel, Field
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey, insert, select, func, or_
from sqlalchemy.exc import IntegrityError
from utils.database import metadata
from datetime import date as d,datetime as dt
from utils.database import database
from utils.logger_utils import log_error
from models.expense_opponent_model import expense_opponents_table
from typing import Annotated

# Define the Purchase model
class Loans(BaseModel):
    date: d #Date of the loan
    creditorName: str
    creditorAddress: str
    creditorNPWP: str | None
    description: str
    received: Annotated[float, Field(ge=0)]
    debt: Annotated[float, Field(ge=0)]
    isPaid: bool = False
    bankAccountName: str
    bankAccountNumber: str
    bankName: str
    createdBy: int | None = None
    createdAt: dt | None = None
    updatedBy: int | None = None
    updatedAt: dt | None = None

    # Initialize the model with default values
    def __init__(self, **data):
        super().__init__(**data)
        if self.createdAt is None:
            self.createdAt = dt.now()
            self.isPaid = False

    async def create(self):
        """
        Create a new bank account in the database.
        
        Returns:
            Dict: A success message with the created bank account ID.
        """
        try:
            query = loans_table.insert().values(
                date=self.date,
                creditorName=self.creditorName,
                creditorAddress=self.creditorAddress,
                creditorNPWP=self.creditorNPWP,
                description=self.description,
                received=self.received,
                debt=self.debt,
                bankAccountName=self.bankAccountName,
                bankAccountNumber=self.bankAccountNumber,
                bankName=self.bankName,
                createdAt=self.createdAt,
                createdBy=self.createdBy,
                updatedAt=None,
                updatedBy=None
            )
            result = await database.execute(query)
            return {"message": "Loan created successfully", "loan_id": result}
        except IntegrityError as e:
            # Handle integrity errors, such as unique constraint violations
            log_error(f"Integrity error while creating loan data: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            # Handle any other exceptions
            log_error(f"Unexpected error while creating loan data: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_loans(isPaid: bool, isUnpaid: bool):
        """
        Create a new bank account in the database.
        
        Returns:
            Dict: A success message with the created bank account ID.
        """
        try:
            query = loans_table.select().where()
            result = await database.execute(query)
            return {"message": "Loan created successfully", "loan_id": result}
        except IntegrityError as e:
            # Handle integrity errors, such as unique constraint violations
            log_error(f"Integrity error while creating loan data: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            # Handle any other exceptions
            log_error(f"Unexpected error while creating loan data: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

# Define the payments table
loans_table = Table(
    "loans",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date", Date, nullable=False),
    Column("creditorName", String, nullable=False),
    Column("creditorAddress", String, nullable=False),
    Column("creditorNPWP", String, default=None, nullable=True),
    Column("description", String, nullable=False, default=""),
    Column("received", Float, nullable=False, default=0),
    Column("debt", Float, nullable=False, default=0),
    Column("bankAccountName", String, nullable=False),
    Column("bankAccountNumber", String, nullable=False),
    Column("bankName", String, nullable=False),
    Column("createdAt", DateTime(), nullable=False, default=dt.now()),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True, default=None,)
)
