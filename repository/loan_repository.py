from sqlalchemy import insert, select, func
from sqlalchemy.exc import IntegrityError
from utils.database import database
from models.loans_model import loans_table
from utils.logger_utils import log_error
from datetime import datetime as dt
from typing import Optional

class LoanRepository:
    @staticmethod
    async def create(loan_data: dict):
        """Create a new loan in the database."""
        try:
            query = loans_table.insert().values(**loan_data)
            result = await database.execute(query)
            return {"loan_id": result}
        except IntegrityError as e:
            log_error(f"Integrity error while creating loan data: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while creating loan data: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_loans(page: int, pageSize: int, isPaid: bool, isUnpaid: bool, sortBy: str, sortByDirection: str, keyword: Optional[str] = None):
        """Fetch loans with flexible filtering for paid/unpaid status."""
        try:
            # Build the where conditions dynamically
            conditions = []
            
            # Handle paid/unpaid filter logic
            if isPaid and not isUnpaid:
                # Only paid loans
                conditions.append(loans_table.c.isPaid == True)
            elif isUnpaid and not isPaid:
                # Only unpaid loans
                conditions.append(loans_table.c.isPaid == False)
            # If both are True or both are False, don't filter by isPaid (show all)
            
            # Handle keyword search
            if keyword is not None and keyword != "":
                conditions.append(loans_table.c.creditorName.ilike(f"%{keyword}%"))
            
            # Build the main query
            query = select(loans_table.c).where(*conditions)
            
            # Apply sorting
            if sortByDirection == "asc":
                query = query.order_by(loans_table.c[sortBy].asc())
            else:
                query = query.order_by(loans_table.c[sortBy].desc())
            
            # Apply pagination
            query = query.limit(pageSize).offset((page) * pageSize)
            result = await database.fetch_all(query)
            
            loan_result = []
            for loan in result:
                loan_dict = dict(loan)
                loan_result.append(loan_dict)
            
            # Build count query with same conditions
            count_query = select(func.count()).select_from(loans_table).where(*conditions)
            count = await database.fetch_val(count_query)
            
            return {
                "data": loan_result,
                "count": count if count is not None else 0,
            }
            
        except IntegrityError as e:
            log_error(f"Integrity error while fetching loan data: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while fetching loan data: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_loan_by_id(loan_id: int):
        """Get a single loan by ID."""
        try:
            query = select(loans_table).where(loans_table.c.id == loan_id)
            result = await database.fetch_one(query)
            return result
        except IntegrityError as e:
            log_error(f"Integrity error while fetching loan data: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while fetching loan data: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update_payment_status(loan_id: int, status: bool, user_id: int):
        """Update the payment status of a loan."""
        try:
            query = (
                loans_table.update()
                .where(loans_table.c.id == loan_id)
                .values(isPaid=status, updatedBy=user_id, updatedAt=dt.now())
            )
            await database.execute(query)
            return {"message": "Loan payment status updated successfully."}
        except IntegrityError as e:
            log_error(f"Integrity error while updating loan data: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while updating loan data: {str(e)}")
            return {"error": "Internal server error.", "status": 500}