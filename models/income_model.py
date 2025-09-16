from pydantic import BaseModel, Field
from datetime import date as d
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey, insert, select, func, or_
from utils.database import metadata, database
from datetime import datetime as dt
from utils.logger_utils import log_error
from sqlalchemy.exc import IntegrityError
from models.expense_opponent_model import expense_opponents_table

class Income(BaseModel):
    id: int | None = Field(default=None, title="ID of the income", ge=1)
    amount: float = Field(..., title="Amount of the income")
    date: d = Field(..., title="Date of the income")
    incomeType: str = Field(title="Income type")
    opponentID: int = Field(title="Opponent ID", ge =1)
    description: str | None = Field(default=None, title="Description of the income")
    isDelete: bool = False  # Flag to indicate if the purchase is deleted
    createdBy: int
    createdAt: dt
    deletedBy: int | None = None
    deletedAt: dt | None = None

    # Initialize the model with default values
    def __init__(self, **data):
        super().__init__(**data)
        if self.createdAt is None:
            self.createdAt = dt.now()
            
    async def create(self):
        """
        Create an income in the database.
        """
        try:
            query = income_table.insert().values(
                description=self.description,
                date=self.date,
                incomeType=self.incomeType,
                amount=self.amount,
                opponentID=self.opponentID,
                isDelete=self.isDelete,
                createdAt=self.createdAt,
                createdBy=self.createdBy,
                deletedAt=self.deletedAt,
                deletedBy=self.deletedBy
            )
            result = await database.execute(query)
            return {"message": "Income created successfully", "incomeID": result}
        except IntegrityError as e:
            # Handle integrity errors, such as unique constraint violations
            log_error(f"Integrity error while creating income data: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            # Handle any other exceptions
            log_error(f"Unexpected error while creating income data: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    async def get_income(page: int, pageSize: int, sortBy: str, sortByDirection: str, keyword: str | None):
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

            conditions = [income_table.c.isDelete == False]

            or_conditions = []
            if(keyword is not None and keyword != ""):
                or_conditions.append(income_table.c.description.ilike(f"%{keyword}%"))
                or_conditions.append(expense_opponents_table.c.name.ilike(f"%{keyword}%"))
                or_conditions.append(expense_opponents_table.c.description.ilike(f"%{keyword}%"))
            conditions.append(or_(*or_conditions))

            # # Sort by, using switch case
            if sortBy == "date":
                order_by = income_table.c.date.desc() if sortByDirection == "desc" else income_table.c.date
            elif sortBy == "amount":
                order_by = (income_table.c.amount).desc() if sortByDirection == "desc" else (income_table.c.amount)
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

            #Count the total number of purchases
            count_query = (
                 select(func.count())
                .where(*conditions)
            )
            count = await database.fetch_val(count_query)

            #Convert the result
            income_result = []
            for income in incomes:
                income_dict = dict(income)
                income_dict["id"] = income_dict.pop("id")
                income_dict["createdAt"] = income_dict.pop("createdAt")
                income_dict["deletedAt"] = income_dict.pop("deletedAt")
                income_dict["createdBy"] = income_dict.pop("createdBy")
                income_dict["opponentID"] = income_dict.pop("opponentID")
                income_dict["opponent"] = {
                    "id": income_dict.pop("opponentID"),
                    "name": income_dict.pop("opponentName"),
                }
                income_result.append(income_dict)

            return {
                "data": income_result,
                "count": count,
            }
        except Exception as e:
            log_error(f"Error fetching expenses: {str(e)}")
            return {"error": str(e), "status": 500}

# Define the SQLAlchemy table
income_table = Table(
    "income",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("description", String(100), nullable=False),
    Column("date", Date(), nullable=False),
    Column("incomeType", String(100), nullable=False),
    Column("amount", Float(2), nullable=False),
    Column("opponentID", Integer, ForeignKey("expense_opponents.id"), nullable=False),
    Column("isDelete", Boolean(), nullable=False, default=False),
    Column("createdAt", DateTime(), nullable=False, default=dt.now()),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True, default=None),
)