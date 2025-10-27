from sqlalchemy import select, func, or_, insert, update
from utils.database import database
from utils.logger_utils import log_error
from models.expense_model import expenses_table
from models.expense_opponent_model import expense_opponents_table
from datetime import datetime as dt

class ExpenseRepository:
    @staticmethod
    async def create(expense_data: dict):
        """
        Create an expense in the database.
        """
        try:
            query = insert(expenses_table).values(expense_data)
            expense_id = await database.execute(query)
            return expense_id
        except Exception as e:
            log_error(f"Error creating expense: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_all(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None, start: dt, end: dt, ignore: bool):
        """
        Retrieve a list of expenses from the database.
        """
        if page < 0:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            offset = page * pageSize

            opponent_columns = [
                expense_opponents_table.c.id.label("opponentID"),
                expense_opponents_table.c.name.label("opponentName")
            ]

            conditions = [expenses_table.c.isDelete == False]
            
            if not ignore:
                conditions.append(expenses_table.c.date >= start)
                conditions.append(expenses_table.c.date <= end)

            or_conditions = []
            if keyword is not None and keyword != "":
                or_conditions.append(expenses_table.c.invoiceName.ilike(f"%{keyword}%"))
                or_conditions.append(expenses_table.c.receiptName.ilike(f"%{keyword}%"))
                or_conditions.append(expenses_table.c.description.ilike(f"%{keyword}%"))
                or_conditions.append(expense_opponents_table.c.name.ilike(f"%{keyword}%"))
                or_conditions.append(expense_opponents_table.c.description.ilike(f"%{keyword}%"))
            
            if or_conditions:
                conditions.append(or_(*or_conditions))

            # Filter conditions
            filter_or_conditions = []
            if filterObject.get("isDue"):
                filter_or_conditions.append(expenses_table.c.dueDate <= dt.now().date())
            if filterObject.get("isNotDue"):
                filter_or_conditions.append(expenses_table.c.dueDate > dt.now().date())
            
            if filter_or_conditions:
                conditions.append(or_(*filter_or_conditions))

            payment_or_conditions = []
            if filterObject.get("isPaid"):
                payment_or_conditions.append(expenses_table.c.isPaid == True)
            if filterObject.get("isUnpaid"):
                payment_or_conditions.append(expenses_table.c.isPaid == False)
            
            if payment_or_conditions:
                conditions.append(or_(*payment_or_conditions))

            # Sort by
            if sortBy == "date":
                order_by = expenses_table.c.date.desc() if sortByDirection == "desc" else expenses_table.c.date.asc()
            elif sortBy == "dueDate":
                order_by = expenses_table.c.dueDate.desc() if sortByDirection == "desc" else expenses_table.c.dueDate.asc()
            elif sortBy == "total":
                order_by = expenses_table.c.dpp.desc() if sortByDirection == "desc" else expenses_table.c.dpp.asc()
            elif sortBy == "invoiceName":
                order_by = expenses_table.c.invoiceName.desc() if sortByDirection == "desc" else expenses_table.c.invoiceName.asc()
            else:
                order_by = expenses_table.c.date.desc()
                
            query = (
                select(*expenses_table.c, *opponent_columns)
                .select_from(expenses_table.join(expense_opponents_table, expenses_table.c.opponentID == expense_opponents_table.c.id, isouter=True))
                .where(*conditions)
                .order_by(order_by)
                .offset(offset)
                .limit(pageSize)
            )
            expenses = await database.fetch_all(query)

            # Count the total number of expenses
            count_query = (
                select(func.count())
                .select_from(expenses_table.join(expense_opponents_table, expenses_table.c.opponentID == expense_opponents_table.c.id, isouter=True))
                .where(*conditions)
            )
            count = await database.fetch_val(count_query)

            # Convert the result
            expense_result = []
            for expense in expenses:
                expense_dict = dict(expense)
                expense_dict["opponent"] = {
                    "id": expense_dict["opponentID"],
                    "name": expense_dict["opponentName"],
                }
                # Remove the individual opponent fields
                del expense_dict["opponentID"]
                del expense_dict["opponentName"]
                expense_result.append(expense_dict)

            return {
                "data": expense_result,
                "count": count,
            }
        except Exception as e:
            log_error(f"Error fetching expenses: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_id(id: int):
        """
        Get an expense by ID.
        """
        try:
            expense_opponent_columns = [
                expense_opponents_table.c.id.label("expense_opponent_id"),
                expense_opponents_table.c.name.label("expense_opponent_name"),
                expense_opponents_table.c.type.label("expense_opponent_type"),
                expense_opponents_table.c.description.label("expense_opponent_description"),
                expense_opponents_table.c.paymentNumber.label("expense_opponent_payment_number"),
            ]
            query = (
                select(*expenses_table.c, *expense_opponent_columns)
                .join(expense_opponents_table, expenses_table.c.opponentID == expense_opponents_table.c.id)
                .where(expenses_table.c.id == id)
            )
            expense = await database.fetch_one(query)

            if not expense:
                return {"error": "Expense not found", "status": 404}

            return dict(expense)
        except Exception as e:
            log_error(f"Error fetching expense by ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def approve_by_id(id: int, userID: int):
        """
        Update expense status to approved.
        """
        try:
            query = (
                expenses_table.update()
                .where(expenses_table.c.id == id)
                .values(
                    isApprove=True,
                    approvedBy=userID,
                    approvedAt=dt.now()
                )
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Expense not found", "status": 404}
            return {"message": "Expense approved successfully"}
        except Exception as e:
            log_error(f"Error approving expense: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update_payment_status(expenseID: int, isPaid: bool, userID: int):
        """
        Update the payment status of an expense.
        """
        try:
            query = (
                expenses_table.update()
                .where(expenses_table.c.id == expenseID)
                .values(
                    isPaid=isPaid,
                    updatedBy=userID,
                    updatedAt=dt.now()
                )
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Expense not found", "status": 404}
            return {"message": "Expense payment status updated successfully"}
        except Exception as e:
            log_error(f"Error updating expense payment status: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update(expense_id: int, expense_data: dict):
        """
        Update an expense in the database.
        """
        try:
            query = (
                expenses_table.update()
                .where(expenses_table.c.id == expense_id)
                .values(expense_data)
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Expense not found", "status": 404}
            return {"message": "Expense updated successfully"}
        except Exception as e:
            log_error(f"Error updating expense: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def delete(expense_id: int, user_id: int):
        """
        Soft delete an expense from the database.
        """
        try:
            query = (
                expenses_table.update()
                .where(expenses_table.c.id == expense_id)
                .values({
                    "isDelete": True,
                    "deletedBy": user_id,
                    "deletedAt": dt.now()
                })
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Expense not found", "status": 404}
            return {"message": "Expense deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting expense: {str(e)}")
            return {"error": str(e), "status": 500}