from pydantic import BaseModel, Field
from typing import Optional, Annotated
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey, insert, select, func, or_
from utils.database import metadata
from datetime import date as d,datetime as dt
from utils.database import database
from utils.logger_utils import log_error
from models.supplier_model import suppliers_table

# Define the Purchase model
class Expense(BaseModel):
    invoiceName: str  # Name of the invoice
    receiptName: str  # Name of the receipt
    taxInvoiceName: str | None = None  # Name of the tax invoice
    supplierID: int  # ID of the supplier
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
            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
            ]

            conditions = [expenses_table.c.isDelete == False]

            or_conditions = []
            if(keyword is not None and keyword != ""):
                or_conditions.append(expenses_table.c.invoiceName.ilike(f"%{keyword}%"))
                or_conditions.append(expenses_table.c.receiptName.ilike(f"%{keyword}%"))
                or_conditions.append(expenses_table.c.taxInvoiceName.ilike(f"%{keyword}%"))
                or_conditions.append(suppliers_table.c.name.ilike(f"%{keyword}%"))
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
            elif sortBy == "supplier":
                order_by = suppliers_table.c.name.desc() if sortByDirection == "desc" else suppliers_table.c.name.asc()
            elif sortBy == "invoiceName":
                order_by = expenses_table.c.invoiceName.desc() if sortByDirection == "desc" else expenses_table.c.invoiceName
            else:
                order_by = expenses_table.c.date.desc()
                
            
            query = (
                select(*expenses_table.c, *supplier_columns)
                .join(suppliers_table, expenses_table.c.supplierID == suppliers_table.c.id)
                .where(*conditions)
                .order_by(order_by)
                .offset(offset)
                .limit(pageSize)
            )
            expenses = await database.fetch_all(query)

            #Count the total number of purchases
            count_query = (
                 select(func.count())
                .select_from(expenses_table.join(suppliers_table, expenses_table.c.supplierID == suppliers_table.c.id))
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
                expense_dict["supplierID"] = expense_dict.pop("supplierID")
                expense_dict["supplier"] = {
                    "id": expense_dict.pop("supplier_id"),
                    "name": expense_dict.pop("supplier_name"),
                    "address": expense_dict.pop("supplier_address"),
                    "city": expense_dict.pop("supplier_city"),
                    "province": expense_dict.pop("supplier_province"),
                    "prefix": expense_dict.pop("supplier_prefix"),
                }
                expense_result.append(expense_dict)
        except Exception as e:
            log_error(f"Error fetching expenses: {str(e)}")
            return {"error": str(e), "status": 500}

# Define the SQLAlchemy table
expenses_table = Table(
    "expenses",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("invoiceName", String(100), nullable=False),
    Column("receiptName", String(100), nullable=False),
    Column("taxInvoiceName", String(100), nullable=True),
    Column("supplierID", Integer, nullable=False),
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