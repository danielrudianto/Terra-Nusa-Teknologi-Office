from pydantic import BaseModel, Field
from datetime import datetime as dt, date as d
from sqlalchemy import Table, Column, Integer, ForeignKey, Float, Date, String
from utils.database import metadata, database

class Mutation(BaseModel):
    id: int | None = Field(default=None, title="ID of the mutation", ge=1)
    bankAccountID: int = Field(..., title="ID of the bank account", ge=1)
    amount: float = Field(..., title="Amount of the mutation")
    date: d = Field(..., title="Date of the mutation")
    description: str | None = Field(default=None, title="Description of the mutation")
    paymentID: int | None = Field(default=None, title="ID of the payment associated with the mutation")
    interpaymentID: int | None = Field(default=None, title="ID of the interpayment associated with the mutation")
    incomeID: int | None = Field(default=None, title="ID of the income associated with the mutation")

    @staticmethod
    async def create_mutation(mutation_data: dict):
        """
        Create a mutation in the database.
        """
        query = mutation_tables.insert().values(**mutation_data)
        try:
            result = await database.execute(query)
            if not result:
                return {"error": "Failed to create mutation", "status": 500}
            
            return {"message": "Mutation created successfully", "mutationID": result.inserted_primary_key[0]}
        except Exception as e:
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def delete_mutations_by_payment_ids(payment_ids: list[int]):
        """
        Delete mutations associated with the given payment IDs.
        """
        if not payment_ids:
            return {"message": f"Deleted 0 mutations successfully"}
        
        query = mutation_tables.delete().where(mutation_tables.c.paymentID.in_(payment_ids))
        try:
            result = await database.execute(query)
            return {"message": f"Deleted {result.rowcount} mutations successfully"}
        except Exception as e:
            return {"error": str(e), "status": 500}

mutation_tables = Table(
    "mutations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("bankAccountID", Integer, ForeignKey("bank_accounts.id"), nullable=False),
    Column("amount", Float, nullable=False),
    Column("date", Date, nullable=False),
    Column("description", String, nullable=True),
    Column("paymentID", Integer, ForeignKey("payments.id"), nullable=True),
    Column("interpaymentID", Integer, ForeignKey("interpayments.id"), nullable=True)
)