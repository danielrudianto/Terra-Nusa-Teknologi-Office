from pydantic import BaseModel, Field
from typing import Optional, Annotated
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey, insert, select, func, or_
from utils.database import metadata
from datetime import date as d,datetime as dt
from utils.database import database
from utils.logger_utils import log_error
from models.expense_opponent_model import expense_opponents_table

# Define the Purchase model
class Expense(BaseModel):
    invoiceName: str  # Name of the invoice
    receiptName: str  # Name of the receipt
    taxInvoiceName: str | None = None  # Name of the tax invoice
    opponentID: int | None # ID of the opponent (optional)
    date: d  # Date of the purchase
    dueDate: d | None = None
    purchaseType: str  # Type of the purchase
    dpp: Annotated[float, Field(ge=0)]  # DPP value (greater than or equal to 0)
    ppn: Annotated[float, Field(ge=0)]  # PPN value (optional)
    pbbkb: Annotated[float, Field(ge=0)]  # PBBKB value (optional)
    pphCode: str | None  # PPH code
    pphTaxObject: str | None  # PPH tax object
    pphPercentage: Annotated[float, Field(ge=0, le=16)]  # PPH percentage (0-10%)
    bankName: str  # Name of the bank
    bankAccountName: str  # Name of the bank account
    bankAccountNumber: str  # Bank account number
    paymentMethod: str  # Payment method
    isPaid: bool = False  # Flag to indicate if the purchase is paid
    isDelete: bool = False  # Flag to indicate if the purchase is deleted
    description: str # Description of the purchase

    @staticmethod
    async def create_expense(expense_data: dict):
        """
        Create an expense in the database.
        """
        try:
            if not expense_data:
                return {"message": "No expense data to create."}
            query = insert(expenses_table).values(expense_data)
            await database.execute(query)
            return {"message": "Expense created successfully"}
        except Exception as e:
            log_error(f"Error creating expense: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_expenses(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None):
        """
        Retrieve a list of expenses from the database.
        """
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            offset = (page - 1) * pageSize

            opponent_columns = [
                expense_opponents_table.c.id.label("opponentID"),
                expense_opponents_table.c.name.label("opponentName")
            ]

            conditions = [expenses_table.c.isDelete == False]

            or_conditions = []
            if(keyword is not None and keyword != ""):
                or_conditions.append(expenses_table.c.invoiceName.ilike(f"%{keyword}%"))
                or_conditions.append(expenses_table.c.receiptName.ilike(f"%{keyword}%"))
                or_conditions.append(expenses_table.c.taxInvoiceName.ilike(f"%{keyword}%"))
                or_conditions.append(expenses_table.c.description.ilike(f"%{keyword}%"))
            conditions.append(or_(*or_conditions))

            or_conditions = []
            if filterObject.get("isDue"):
                or_conditions.append(expenses_table.c.dueDate <= dt.now().date())
            if filterObject.get("isNotDue"):
                or_conditions.append(expenses_table.c.dueDate > dt.now().date())

            conditions.append(or_(*or_conditions))

            or_conditions = []
            if filterObject.get("isPaid"):
                or_conditions.append(expenses_table.c.isPaid == True)
            if filterObject.get("isUnpaid"):
                or_conditions.append(expenses_table.c.isPaid == False)

            conditions.append(or_(*or_conditions))

            # # Sort by, using switch case
            if sortBy == "date":
                order_by = expenses_table.c.date.desc() if sortByDirection == "desc" else expenses_table.c.date
            elif sortBy == "dueDate":
                order_by = expenses_table.c.dueDate.desc() if sortByDirection == "desc" else expenses_table.c.dueDate
            elif sortBy == "total":
                order_by = (expenses_table.c.ppn + expenses_table.c.dpp).desc() if sortByDirection == "desc" else (expenses_table.c.ppn + expenses_table.c.dpp)
            elif sortBy == "invoiceName":
                order_by = expenses_table.c.invoiceName.desc() if sortByDirection == "desc" else expenses_table.c.invoiceName
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

            #Count the total number of purchases
            count_query = (
                 select(func.count())
                .where(*conditions)
            )
            count = await database.fetch_val(count_query)

            #Convert the result
            expense_result = []
            for expense in expenses:
                expense_dict = dict(expense)
                expense_dict["id"] = expense_dict.pop("id")
                expense_dict["createdAt"] = expense_dict.pop("createdAt")
                expense_dict["updatedAt"] = expense_dict.pop("updatedAt")
                expense_dict["deletedAt"] = expense_dict.pop("deletedAt")
                expense_dict["createdBy"] = expense_dict.pop("createdBy")
                expense_dict["opponentID"] = expense_dict.pop("opponentID")
                expense_dict["opponent"] = {
                    "id": expense_dict.pop("opponentID"),
                    "name": expense_dict.pop("opponentName"),
                }
                expense_result.append(expense_dict)

            return {
                "data": expense_result,
                "count": count,
            }
        except Exception as e:
            log_error(f"Error fetching expenses: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_expense_by_id(id: int):
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

            return expense
        except Exception as e:
            log_error(f"Error fetching expense by ID: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def update_payment_status(expenseID: int, isPaid: bool, userID: int):
        """
        Update the payment status of a expense.
        """
        try:
            query = (
                expenses_table.update()
                .where(
                    expenses_table.c.id == expenseID,
                )
                .values(
                    isPaid=isPaid,
                )
            )
            await database.execute(query)
            return {"message": f"Expense updated successfully"}
        except Exception as e:
            log_error(f"Error updating expense payment status: {str(e)}")
            return {"error": str(e), "status": 500}


# Define the SQLAlchemy table
expenses_table = Table(
    "expenses",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("invoiceName", String(100), nullable=False),
    Column("receiptName", String(100), nullable=False),
    Column("taxInvoiceName", String(100), nullable=True),
    Column("opponentID", Integer, ForeignKey("expense_opponents.id"), nullable=True),
    Column("date", Date(), nullable=False),
    Column("dueDate", Date(), nullable=True),
    Column("purchaseType", String(100), nullable=False),
    Column("dpp", Float(), nullable=False),
    Column("ppn", Float(), nullable=False),
    Column("pbbkb", Float(), nullable=False),
    Column("pphCode", String(100), nullable=True),
    Column("pphTaxObject", String(500), nullable=True),
    Column("pphPercentage", Float(), nullable=False),
    Column("bankName", String(100), nullable=False),
    Column("bankAccountName", String(100), nullable=False),
    Column("bankAccountNumber", String(100), nullable=False),
    Column("paymentMethod", String(100), nullable=False),
    Column("description", String(500), nullable=False),
    Column("isPaid", Boolean(), nullable=False, default=False),
    Column("isDelete", Boolean(), nullable=False, default=False),
    Column("createdAt", DateTime(), nullable=False, default=dt.now()),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
)