from sqlalchemy import select, func, or_, insert, update
from utils.database import database
from utils.logger_utils import log_error
from models.expense_opponent_model import expense_opponents_table
from datetime import datetime as dt

class ExpenseOpponentRepository:
    @staticmethod
    async def create(opponent_data: dict):
        """
        Create an expense opponent in the database.
        """
        try:
            if not opponent_data:
                return {"error": "No expense opponent data to create.", "status": 400}
            
            query = insert(expense_opponents_table).values(opponent_data)
            opponent_id = await database.execute(query)
            return {"message": "Expense opponent created successfully", "opponent_id": opponent_id}
        except Exception as e:
            log_error(f"Error creating expense opponent: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_all(page: int, pageSize: int, sortBy: str | None, sortByDirection: str | None, keyword: str | None):
        """
        Retrieve a list of expense opponents from the database.
        """
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            offset = (page - 1) * pageSize
            conditions = [expense_opponents_table.c.isDelete == False]

            or_conditions = []
            if keyword is not None and keyword != "":
                or_conditions.append(expense_opponents_table.c.name.ilike(f"%{keyword}%"))
                or_conditions.append(expense_opponents_table.c.type.ilike(f"%{keyword}%"))
                or_conditions.append(expense_opponents_table.c.description.ilike(f"%{keyword}%"))
                or_conditions.append(expense_opponents_table.c.paymentNumber.ilike(f"%{keyword}%"))
            
            if or_conditions:
                conditions.append(or_(*or_conditions))

            # Default order by name if no sort specified
            if sortBy == "name":
                order_by = expense_opponents_table.c.name.desc() if sortByDirection == "desc" else expense_opponents_table.c.name.asc()
            else:
                order_by = expense_opponents_table.c.name.asc()

            query = (
                select(expense_opponents_table)
                .where(*conditions)
                .order_by(order_by)
                .offset(offset)
                .limit(pageSize)
            )
            expense_opponents = await database.fetch_all(query)

            # Count the total number of expense opponents
            count_query = (
                select(func.count())
                .select_from(expense_opponents_table)
                .where(*conditions)
            )
            count = await database.fetch_val(count_query)

            return {
                "data": [dict(opponent) for opponent in expense_opponents],
                "count": count
            }
        except Exception as e:
            log_error(f"Error retrieving expense opponents: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_id(opponent_id: int):
        """
        Get an expense opponent by ID.
        """
        try:
            query = (
                select(expense_opponents_table)
                .where(
                    expense_opponents_table.c.id == opponent_id,
                    expense_opponents_table.c.isDelete == False
                )
            )
            opponent = await database.fetch_one(query)
            
            if not opponent:
                return {"error": "Expense opponent not found", "status": 404}
            
            return dict(opponent)
        except Exception as e:
            log_error(f"Error retrieving expense opponent by ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update(opponent_id: int, opponent_data: dict):
        """
        Update an expense opponent in the database.
        """
        try:
            query = (
                update(expense_opponents_table)
                .where(
                    expense_opponents_table.c.id == opponent_id,
                    expense_opponents_table.c.isDelete == False
                )
                .values(opponent_data)
            )
            
            result = await database.execute(query)
            if result == 0:
                return {"error": "Expense opponent not found", "status": 404}
            
            return {"message": "Expense opponent updated successfully"}
        except Exception as e:
            log_error(f"Error updating expense opponent: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def delete(opponent_id: int, user_id: int):
        """
        Soft delete an expense opponent from the database.
        """
        try:
            query = (
                update(expense_opponents_table)
                .where(
                    expense_opponents_table.c.id == opponent_id,
                    expense_opponents_table.c.isDelete == False
                )
                .values({
                    "isDelete": True,
                    "deletedBy": user_id,
                    "deletedAt": dt.now()
                })
            )
            
            result = await database.execute(query)
            if result == 0:
                return {"error": "Expense opponent not found", "status": 404}
            
            return {"message": "Expense opponent deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting expense opponent: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def search_by_name(keyword: str, limit: int = 10):
        """
        Search expense opponents by name.
        """
        try:
            query = (
                select(expense_opponents_table.c.id, expense_opponents_table.c.name)
                .where(
                    expense_opponents_table.c.name.ilike(f"%{keyword}%"),
                    expense_opponents_table.c.isDelete == False
                )
                .limit(limit)
            )
            
            opponents = await database.fetch_all(query)
            return [dict(opponent) for opponent in opponents]
        except Exception as e:
            log_error(f"Error searching expense opponents: {str(e)}")
            return {"error": str(e), "status": 500}