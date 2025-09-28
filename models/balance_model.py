from pydantic import BaseModel, Field
from datetime import datetime as dt, date as d
from sqlalchemy import Table, Column, Integer, ForeignKey, Float, Date, String, select, func
from utils.database import metadata, database, engine
from utils.logger_utils import log_error

class Balance(BaseModel):
    id: int = Field(..., title="ID of the bank account", ge=1)
    balance: float = Field(..., title="Amount of the mutation")

    @staticmethod
    async def fetch_by_bank_account_ids(ids: list[int]):
        try:
            query = balance_view.select().where(balance_view.c.id.in_(ids))
            result = await database.fetch_all(query)

            return [
                {"id": row["id"], "balance": row["balance"]}
                for row in result
            ]
        except Exception as e:
            log_error(f"Error fetching bank accounts: {str(e)}")
            return {"error": str(e), "status": 500}

balance_view = Table(
    "balance",
    metadata,
    autoload_with=engine,
)