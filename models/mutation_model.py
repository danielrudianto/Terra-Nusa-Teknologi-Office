from pydantic import BaseModel, Field
from datetime import datetime as dt, date as d
from sqlalchemy import Table, Column, Integer, ForeignKey, Float, Date, String, select, func, and_
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
            query = mutation_view.select().where(mutation_view.c.bankaccountid == bankAccountID, mutation_view.c.date >= startDate, mutation_view.c.date <= endDate).limit(pageSize).offset((page - 1) * pageSize)
            result = await database.fetch_all(query)

            count_query = select(func.count()).select_from(mutation_view).where(mutation_view.c.bankaccountid == bankAccountID, mutation_view.c.date >= startDate, mutation_view.c.date <= endDate)
            count = await database.fetch_val(count_query)
            return {"data": result, "count": count if count is not None else 0}
        except Exception as e:
            log_error(f"Error fetching bank accounts: {str(e)}")
            return {"error": str(e), "status": 500}
        
    async def download_mutation(bankAccountID: int, month: int, year: int):
        try:
            query = mutation_view.select().where(mutation_view.c.bankaccountid == bankAccountID, func.extract('month', mutation_view.c.date) == month, func.extract('year', mutation_view.c.date) == year)
            result = await database.fetch_all(query)
            return result
        except Exception as e:
            log_error(f"Error downloading bank account mutation: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def fetch_by_month_year(month: int, year: int, bank_account_ids: list[int] = None):
        """
        Fetch the latest balance for each bank account before the start of the month
        Considering both date and sortOrder to get the true last transaction
        """
        try:
            from datetime import date
            
            start_of_month = date(year, month, 1)
            
            if bank_account_ids is None:
                sql = """
                SELECT m.bankaccountid, m.balance
                FROM mutation m
                JOIN (
                    SELECT 
                        bankaccountid,
                        MAX(CONCAT(date,'-',LPAD(sortorder,2,'0'),'-',LPAD(tiebreaker,10,'0'))) AS max_key
                    FROM mutation
                    WHERE date <= :start_date
                    GROUP BY bankaccountid
                ) last_row 
                ON m.bankaccountid = last_row.bankaccountid
                AND CONCAT(m.date,'-',LPAD(m.sortorder,2,'0'),'-',LPAD(m.tiebreaker,10,'0')) = last_row.max_key;

                """
                params = {"start_date": start_of_month}
            else:
                sql = """
                SELECT bankAccountID, balance
                FROM (
                    SELECT 
                        bankAccountID, 
                        balance,
                        date,
                    FROM mutation 
                    WHERE date < :start_date AND bankAccountID IN :bank_account_ids
                ) ranked
                """
                params = {"start_date": start_of_month, "bank_account_ids": tuple(bank_account_ids)}
                
            
            result = await database.fetch_all(sql, params)
            total_balance = 0
            for row in result:
                data = dict(row)
                total_balance += data["balance"]
            
            return total_balance
            
        except Exception as e:
            log_error(f"Error fetching bank account balances: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def download_calendar_data(month: int, year: int, bank_account_ids: list[int] = None):
        """
        Fetch the latest balance for each bank account before the start of the month
        Considering both date and sortOrder to get the true last transaction
        """
        try:
            from datetime import date
            
            start_of_month = date(year, month, 1)
            
            if bank_account_ids is None:
                sql = """
                SELECT m.bankaccountid, m.balance
                FROM mutation m
                JOIN (
                    SELECT 
                        bankaccountid,
                        MAX(CONCAT(date,'-',LPAD(sortorder,2,'0'),'-',LPAD(tiebreaker,10,'0'))) AS max_key
                    FROM mutation
                    WHERE date <= :start_date
                    GROUP BY bankaccountid
                ) last_row 
                ON m.bankaccountid = last_row.bankaccountid
                AND CONCAT(m.date,'-',LPAD(m.sortorder,2,'0'),'-',LPAD(m.tiebreaker,10,'0')) = last_row.max_key;

                """
                params = {"start_date": start_of_month}
            else:
                sql = """
                SELECT bankAccountID, balance
                FROM (
                    SELECT 
                        bankAccountID, 
                        balance,
                        date,
                    FROM mutation 
                    WHERE date < :start_date AND bankAccountID IN :bank_account_ids
                ) ranked
                """
                params = {"start_date": start_of_month, "bank_account_ids": tuple(bank_account_ids)}
                
            
            result = await database.fetch_all(sql, params)
            return result
            
        except Exception as e:
            log_error(f"Error fetching bank account balances: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def download_income_data(month: int, year:int, bank_account_ids: list[int] = None):
        try:
            if month < 1 or month > 12:
                return {"error": "Invalid month", "status": 400}
            if year < 2020:
                return {"error": "Invalid year", "status": 400}

            conditions = [
                func.extract('month', mutation_view.c.date) == month,
                func.extract('year', mutation_view.c.date) == year,
            ]

            if mutation_view and len(bank_account_ids) > 0:
                conditions.append(
                    mutation_view.c.bankaccountid.in_(bank_account_ids)
                )

            query = (
                select(
                    mutation_view.c.date,
                    mutation_view.c.amount,
                    mutation_view.c.bankaccountid,
                    mutation_view.c.opponent,
                    mutation_view.c.document,
                    mutation_view.c.reference,
                    mutation_view.c.sortorder,
                    mutation_view.c.tiebreaker,
                )
                .where(and_(*conditions))
                .order_by(
                    mutation_view.c.bankaccountid,
                    mutation_view.c.date,
                    mutation_view.c.sortorder,
                    mutation_view.c.tiebreaker,
                )
            )

            rows = await database.fetch_all(query)

            result = {}

            for row in rows:
                bank_id = row.bankaccountid

                if bank_id not in result:
                    result[bank_id] = []

                result[bank_id].append({
                    "date": row.date,
                    "amount": float(row.amount or 0),
                    "opponent": row.opponent,
                    "document": row.document,
                    "reference": row.reference,
                })

            return {
                "status": 200,
                "data": result
            }

        except Exception as e:
            return {"error": str(e), "status": 500}

mutation_view = Table(
    "mutation",
    metadata,
    autoload_with=engine,
)