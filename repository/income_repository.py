from sqlalchemy import select, func, or_, insert
from utils.database import database
from utils.logger_utils import log_error
from models.income_model import income_table
from models.expense_opponent_model import expense_opponents_table
from sqlalchemy.exc import IntegrityError
from datetime import datetime as dt
from utils.errors import internal_error

class IncomeRepository:
    @staticmethod
    async def create(income_data: dict):
        """
        Create an income in the database.
        """
        try:
            query = income_table.insert().values(
                description=income_data.get('description'),
                date=income_data.get('date'),
                incomeType=income_data.get('incomeType'),
                amount=income_data.get('amount'),
                opponentID=income_data.get('opponentID'),
                isDelete=income_data.get('isDelete', False),
                createdAt=income_data.get('createdAt'),
                createdBy=income_data.get('createdBy'),
                deletedAt=income_data.get('deletedAt'),
                deletedBy=income_data.get('deletedBy')
            )
            result = await database.execute(query)
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="income",
                entityID=result,
                action="create",
            )
            return {"message": "Income created successfully", "incomeID": result}
        except IntegrityError as e:
            log_error(f"Integrity error while creating income data: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while creating income data: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_all(page: int, pageSize: int, sortBy: str, startDate: dt, endDate: dt, sortByDirection: str, keyword: str | None, ignore: bool):
        """
        Retrieve a list of incomes from the database.
        """
        if page < 0:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            offset = (page) * pageSize

            opponent_columns = [
                expense_opponents_table.c.id.label("opponentID"),
                expense_opponents_table.c.name.label("opponentName")
            ]

            conditions = [income_table.c.isDelete == False]
            if(ignore == False):
                # Add these conditions
                #income_table.c.date >= startDate, income_table.c.date <= endDate
                conditions.append(income_table.c.date >= startDate)
                conditions.append(income_table.c.date <= endDate)

            or_conditions = []
            if keyword is not None and keyword != "":
                or_conditions.append(income_table.c.description.ilike(f"%{keyword}%"))
                or_conditions.append(expense_opponents_table.c.name.ilike(f"%{keyword}%"))
                or_conditions.append(expense_opponents_table.c.description.ilike(f"%{keyword}%"))
            
            if or_conditions:
                conditions.append(or_(*or_conditions))

            # Sort by, using switch case
            if sortBy == "date":
                order_by = income_table.c.date.desc() if sortByDirection == "desc" else income_table.c.date.asc()
            elif sortBy == "amount":
                order_by = income_table.c.amount.desc() if sortByDirection == "desc" else income_table.c.amount.asc()
            else:
                order_by = income_table.c.date.desc()
                
            query = (
                select(*income_table.c, *opponent_columns)
                .select_from(income_table.join(expense_opponents_table, income_table.c.opponentID == expense_opponents_table.c.id, isouter=True))
                .where(*conditions)
                .order_by(order_by)
                .offset(offset)
                .limit(pageSize)
            )
            incomes = await database.fetch_all(query)
            print(incomes)

            # Count the total number of incomes
            count_query = (
                select(func.count())
                .select_from(income_table.join(expense_opponents_table, income_table.c.opponentID == expense_opponents_table.c.id, isouter=True))
                .where(*conditions)
            )
            count = await database.fetch_val(count_query)

            # Convert the result
            income_result = []
            for income in incomes:
                income_dict = dict(income)
                income_dict["id"] = income_dict["id"]
                income_dict["createdAt"] = income_dict["createdAt"]
                income_dict["deletedAt"] = income_dict["deletedAt"]
                income_dict["createdBy"] = income_dict["createdBy"]
                income_dict["opponent"] = {
                    "id": income_dict["opponentID"],
                    "name": income_dict["opponentName"],
                }
                # Remove the individual opponent fields
                del income_dict["opponentID"]
                del income_dict["opponentName"]
                income_result.append(income_dict)

            return {
                "data": income_result,
                "count": count,
            }
        except Exception as e:
            log_error(f"Error fetching incomes: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_by_id(income_id: int):
        """
        Get a single income by ID.
        """
        try:
            opponent_columns = [
                expense_opponents_table.c.id.label("opponentID"),
                expense_opponents_table.c.name.label("opponentName"),
                expense_opponents_table.c.description.label("opponentDescription")
            ]

            query = (
                select(*income_table.c, *opponent_columns)
                .select_from(income_table.join(expense_opponents_table, income_table.c.opponentID == expense_opponents_table.c.id, isouter=True))
                .where(income_table.c.id == income_id, income_table.c.isDelete == False)
            )
            
            income = await database.fetch_one(query)
            if not income:
                return {"error": "Income not found", "status": 404}

            income_dict = dict(income)
            income_dict["opponent"] = {
                "id": income_dict["opponentID"],
                "name": income_dict["opponentName"],
                "description": income_dict["opponentDescription"]
            }
            del income_dict["opponentID"]
            del income_dict["opponentName"]

            return income_dict
        except Exception as e:
            log_error(f"Error fetching income by ID: {str(e)}")
            return internal_error()

    @staticmethod
    async def update(income_id: int, income_data: dict):
        """
        Update an income in the database.
        """
        try:
            # Keadaan sebelum & sesudah dibandingkan agar nilai lama ikut
            # terekam; tanpa ini audit hanya tahu "diubah", bukan "dari apa".
            _sebelum = await database.fetch_one(
                select(income_table).where(income_table.c.id == income_id)
            )
            # Remove None values
            update_data = {k: v for k, v in income_data.items() if v is not None}
            
            if not update_data:
                return {"error": "No data to update", "status": 400}

            query = (
                income_table.update()
                .where(income_table.c.id == income_id, income_table.c.isDelete == False)
                .values(update_data)
            )
            
            result = await database.execute(query)
            if result == 0:
                return {"error": "Income not found", "status": 404}
                
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="income",
                entityID=income_id,
                action="update",
                changes=AuditLogRepository.diff(
                    dict(_sebelum) if _sebelum else {},
                    dict(
                        await database.fetch_one(
                            select(income_table).where(
                                income_table.c.id == income_id
                            )
                        )
                        or {}
                    ),
                ),
            )

            return {"message": "Income updated successfully"}
        except Exception as e:
            log_error(f"Error updating income: {str(e)}")
            return internal_error()

    @staticmethod
    async def delete(income_id: int, user_id: int):
        """
        Soft delete an income from the database.
        """
        try:
            query = (
                income_table.update()
                .where(income_table.c.id == income_id, income_table.c.isDelete == False)
                .values({
                    "isDelete": True,
                    "deletedBy": user_id,
                    "deletedAt": dt.now()
                })
            )
            
            result = await database.execute(query)
            if result == 0:
                return {"error": "Income not found", "status": 404}
                
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="income",
                entityID=income_id,
                action="delete",
                userID=user_id,
            )
            
            return {"message": "Income deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting income: {str(e)}")
            return internal_error()