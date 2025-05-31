from pydantic import BaseModel
from sqlalchemy import Table, Column, Integer, String, ForeignKey, insert, Boolean, DateTime, select, or_, func
from datetime import datetime as dt
from utils.database import metadata, database
from utils.logger_utils import log_error

class ExpenseOpponent(BaseModel):
    """
    Represents an expense opponent in the system.
    """
    id: int | None = None  # Unique ID for the expense opponent
    name: str  # Name of the expense opponent
    type: str # Type of expense opponent (e.g., individual, company)
    description: str  # Description of the expense opponent
    paymentNumber: str  # Payment number associated with the expense opponent
    
    @staticmethod
    async def create_expense_opponent(opponent_data: dict):
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
    async def get_expense_opponents(page: int, pageSize: int, sortBy: str | None, sortByDirection: str | None, keyword: str | None):
        """
        Retrieve a list of expense opponents from the database.
        """
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        offset = (page - 1) * pageSize
        conditions = [expense_opponents_table.c.isDelete == False]

        or_conditions = []
        if(keyword is not None and keyword != ""):
            or_conditions.append(expense_opponents_table.c.name.ilike(f"%{keyword}%"))
            or_conditions.append(expense_opponents_table.c.type.ilike(f"%{keyword}%"))
            or_conditions.append(expense_opponents_table.c.description.ilike(f"%{keyword}%"))
            or_conditions.append(expense_opponents_table.c.paymentNumber.ilike(f"%{keyword}%"))
        
        conditions.append(or_(*or_conditions))

        if sortBy == "name":
            order_by = expense_opponents_table.c.name.desc() if sortByDirection == "desc" else expense_opponents_table.c.name
        
        try:
            query = (
                select(*expense_opponents_table.c)
                .where(*conditions)
                .order_by(order_by)
                .offset(offset)
                .limit(pageSize)
            )
            expense_opponents = await database.fetch_all(query)

            #Count the total number of purchases
            count_query = (
                select(func.count())
                .select_from(expense_opponents_table)
                .where(*conditions)
            )
            count = await database.fetch_val(count_query)

            return {"data": expense_opponents, "count": count}
        except Exception as e:
            log_error(f"Error retrieving expense opponents: {str(e)}")
            return {"error": str(e), "status": 500}
        
expense_opponents_table = Table(
    'expense_opponents',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('name', String(255), nullable=False),
    Column('type', String(50), nullable=False),
    Column('description', String(500), nullable=True),
    Column('paymentNumber', String(50), nullable=True),
    Column('createdAt', DateTime(), nullable=False, default=dt.today()),
    Column('createdBy', Integer, ForeignKey('users.id'), nullable=False),
    Column('updatedAt', DateTime(), nullable=True, default=None),
    Column('updatedBy', Integer, ForeignKey('users.id'), nullable=True, default=None),
    Column('isDelete', Boolean, default=False),
    Column('deletedAt', DateTime(), nullable=True, default=None),
    Column('deletedBy', Integer, ForeignKey('users.id'), nullable=True, default=None),
)