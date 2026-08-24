from sqlalchemy import insert, select, func, and_, or_
from utils.database import database
from models.interpayment_model import interpayment_table
from models.bank_model import bank_accounts_table
from models.user_model import users_table
from utils.logger_utils import log_error, log_info
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
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="interpayments",
                entityID=result,
                action="create",
            )
            
            if not result:
                return {"error": "Failed to create interpayment", "status": 500}
            
            return {"interpaymentID": result}
        except Exception as e:
            log_error(f"Error creating interpayment: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    async def get_by_id(interpaymentID: int):
        try:
            query = interpayment_table.select().where(interpayment_table.c.id == interpaymentID)
            result = await database.fetch_one(query)
            return result
        except Exception as e:
            log_error(f"Error fetching interpayment {interpaymentID}: {str(e)}")
            return None
        
    @staticmethod
    async def get_detail_by_id(interpaymentID: int):
        """Full detail of a single interpayment: bank accounts on both sides,
        plus audit info (who created / deleted it, and when).

        Deleted rows are returned too — the view dialog shows them with a
        'Deleted' badge rather than pretending they don't exist.
        """
        origin_bank_alias = bank_accounts_table.alias("origin_bank")
        destination_bank_alias = bank_accounts_table.alias("destination_bank")
        created_user_alias = users_table.alias("created_user")
        deleted_user_alias = users_table.alias("deleted_user")

        select_columns = [
            interpayment_table,
            origin_bank_alias.c.bankName.label("originBankName"),
            origin_bank_alias.c.bankAccountName.label("originBankAccountName"),
            origin_bank_alias.c.bankAccountNumber.label("originBankAccountNumber"),
            destination_bank_alias.c.bankName.label("destinationBankName"),
            destination_bank_alias.c.bankAccountName.label("destinationBankAccountName"),
            destination_bank_alias.c.bankAccountNumber.label("destinationBankAccountNumber"),
            created_user_alias.c.name.label("createdByName"),
            created_user_alias.c.email.label("createdByEmail"),
            deleted_user_alias.c.name.label("deletedByName"),
            deleted_user_alias.c.email.label("deletedByEmail"),
        ]

        try:
            query = (
                select(*select_columns)
                .join(
                    origin_bank_alias,
                    interpayment_table.c.bankAccountIDOrigin == origin_bank_alias.c.id,
                    isouter=True,
                )
                .join(
                    destination_bank_alias,
                    interpayment_table.c.bankAccountIDDestination == destination_bank_alias.c.id,
                    isouter=True,
                )
                .join(
                    created_user_alias,
                    interpayment_table.c.createdBy == created_user_alias.c.id,
                    isouter=True,
                )
                .join(
                    deleted_user_alias,
                    interpayment_table.c.deletedBy == deleted_user_alias.c.id,
                    isouter=True,
                )
                .where(interpayment_table.c.id == interpaymentID)
            )

            row = await database.fetch_one(query)
            if row is None:
                return {"error": "Interpayment not found", "status": 404}

            return {"interpayment": dict(row)}
        except Exception as e:
            log_error(f"Error fetching interpayment detail: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def delete(interpaymentID: int, userID: int):
        """Delete an interpayment from the database."""
        try:
            query = interpayment_table.update().where(interpayment_table.c.id == interpaymentID).values(isDelete=True, deletedAt=datetime.now(), deletedBy=userID)
            await database.execute(query)
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="interpayments",
                entityID=interpaymentID,
                action="delete",
                userID=userID,
            )
            
            return {"message": "Interpayment deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting interpayment: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

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
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_calendar_data(month: int, year: int, bankAccountID: list[int] | None):
        """Retrieve interpayments for calendar view."""
        log_info("Retrieving interpayments for month: {}, year: {}".format(month, year))

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

        # 🔥 FILTER REKENING (PENTING)
        if bankAccountID:
            conditions.append(
                or_(
                    interpayment_table.c.bankAccountIDOrigin.in_(bankAccountID),
                    interpayment_table.c.bankAccountIDDestination.in_(bankAccountID),
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
            log_error(f"Error fetching interpayment calendar data: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

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
            return {"error": "Internal server error.", "status": 500}