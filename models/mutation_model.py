from pydantic import BaseModel, Field
from datetime import datetime as dt, date as d
from sqlalchemy import Table, Column, Integer, ForeignKey, Float, Date, String, select, func
from utils.database import metadata, database, engine
from utils.logger_utils import log_error

class Mutation(BaseModel):
    bankAccountID: int = Field(..., title="ID of the bank account", ge=1)
    amount: float = Field(..., title="Amount of the mutation")
    date: d = Field(..., title="Date of the mutation")
    type: str = Field(..., title="Purchase type or income type")
    opponent: str = Field(..., title="Opponent of this transaction")
    document: str= Field(...,title="Underlying document")
    balance: float = Field(..., title="Balance of the mutation line")

    @staticmethod
    async def fetch_mutation(bankAccountID: int, page: int, pageSize: int, startDate: d, endDate: d):
        try:
            query = mutation_view.select().where(mutation_view.c.bankAccountID == bankAccountID, mutation_view.c.date >= startDate, mutation_view.c.date <= endDate).limit(pageSize).offset((page - 1) * pageSize)
            result = await database.fetch_all(query)

            count_query = select(func.count()).select_from(mutation_view).where(mutation_view.c.bankAccountID == bankAccountID, mutation_view.c.date >= startDate, mutation_view.c.date <= endDate)
            count = await database.fetch_val(count_query)

            return {"data": result, "count": count if count is not None else 0}
        except Exception as e:
            log_error(f"Error fetching bank accounts: {str(e)}")
            return {"error": str(e), "status": 500}

mutation_view = Table(
    "mutation",
    metadata,
    autoload_with=engine,
)