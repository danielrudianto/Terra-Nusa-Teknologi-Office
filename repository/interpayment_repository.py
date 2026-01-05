from sqlalchemy import insert, select, func, and_, or_
from utils.database import database
from models.interpayment_model import interpayment_table
from models.bank_model import bank_accounts_table
from utils.logger_utils import log_error
from datetime import datetime

class InterpaymentRepository:
    @staticmethod
    async def create(interpayment_data: dict):
        """Create an interpayment in the database."""
        try:
            if not interpayment_data:
                return {"error": "No interpayment data to create", "status": 400}
            
            query = insert(interpayment_table).values(interpayment_data)
            result = await database.execute(query)
            
            if not result:
                return {"error": "Failed to create interpayment", "status": 500}
            
            return {"interpaymentID": result}
        except Exception as e:
            log_error(f"Error creating interpayment: {str(e)}")
            return {"error": str(e), "status": 500}

    async def get_by_id(interpaymentID: int):
        try:
            query = interpayment_table.select().where(interpayment_table.c.id == interpaymentID)
            result = await database.fetch_one(query)
            return result
        except Exception as e:
            log_error(f"Error fetching interpayment {interpaymentID}: {str(e)}")
            return None

    @staticmethod
    async def delete(interpaymentID: int, userID: int):
        """Delete an interpayment from the database."""
        try:
            query = interpayment_table.update().where(interpayment_table.c.id == interpaymentID).values(isDelete=True, deletedAt=datetime.now(), deletedBy=userID)
            await database.execute(query)
            return {"message": "Interpayment deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting interpayment: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_interpayments(page: int, pageSize: int, startDate: datetime, endDate: datetime, filterObject: dict, sortBy: str, sortByDirection: str):
        """Retrieve a list of interpayments from the database."""
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        # Bank account table aliases
        origin_bank_alias = bank_accounts_table.alias("origin_bank")
        destination_bank_alias = bank_accounts_table.alias("destination_bank")

        select_columns = [
            interpayment_table,
            origin_bank_alias.c.bankName.label("originBankName"),
            origin_bank_alias.c.bankAccountName.label("originBankAccountName"),
            origin_bank_alias.c.bankAccountNumber.label("originBankAccountNumber"),
            destination_bank_alias.c.bankName.label("destinationBankName"),
            destination_bank_alias.c.bankAccountName.label("destinationBankAccountName"),
            destination_bank_alias.c.bankAccountNumber.label("destinationBankAccountNumber"),
        ]

        conditions = [
            interpayment_table.c.isDelete == False, 
            interpayment_table.c.date >= startDate, 
            interpayment_table.c.date <= endDate
        ]
        
        try:
            offset = (page - 1) * pageSize
            query = (
                select(*select_columns)
                .join(
                    origin_bank_alias,
                    interpayment_table.c.bankAccountIDOrigin == origin_bank_alias.c.id,
                    isouter=True
                )
                .join(
                    destination_bank_alias,
                    interpayment_table.c.bankAccountIDDestination == destination_bank_alias.c.id,
                    isouter=True
                )
                .where(and_(*conditions))
                .offset(offset)
                .limit(pageSize)
                .order_by(getattr(interpayment_table.c, sortBy).desc() if sortByDirection == "desc" else getattr(interpayment_table.c, sortBy))
            )
            result = await database.fetch_all(query)

            # Count total records
            count_query = select(func.count()).select_from(interpayment_table).where(and_(*conditions))
            total_count = await database.fetch_val(count_query)
            
            return {
                "data": [dict(row) for row in result],
                "count": total_count,
            }
        except Exception as e:
            log_error(f"Error fetching interpayments: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_calendar_data(month: int, year: int, bankAccountID: list[int]):
        """Retrieve interpayments for calendar view."""
        origin_bank_alias = bank_accounts_table.alias("origin_bank")
        destination_bank_alias = bank_accounts_table.alias("destination_bank")

        select_columns = [
            interpayment_table,
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
                    isouter=True
                )
                .join(
                    destination_bank_alias,
                    interpayment_table.c.bankAccountIDDestination == destination_bank_alias.c.id,
                    isouter=True
                )
                .where(and_(*conditions))
            )
            result = await database.fetch_all(query)
            return [dict(row) for row in result]
        except Exception as e:
            log_error(f"Error fetching interpayment calendar data: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_calendar_data_by_date(date: int, month: int, year: int, bankAccountID: list[int] | None):
        """Retrieve interpayments for specific date in calendar view."""
        origin_bank_alias = bank_accounts_table.alias("origin_bank")
        destination_bank_alias = bank_accounts_table.alias("destination_bank")

        select_columns = [
            interpayment_table,
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
                    isouter=True
                )
                .join(
                    destination_bank_alias,
                    interpayment_table.c.bankAccountIDDestination == destination_bank_alias.c.id,
                    isouter=True
                )
                .where(and_(*conditions))
            )
            result = await database.fetch_all(query)
            return [dict(row) for row in result]
        except Exception as e:
            log_error(f"Error fetching interpayment calendar data by date: {str(e)}")
            return {"error": str(e), "status": 500}