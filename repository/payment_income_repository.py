from sqlalchemy import insert, select, func
from typing import List, Optional
from utils.database import database
from models.payment_incoming_model import payment_incoming_table
from utils.logger_utils import log_error, log_info
from datetime import datetime

class PaymentIncomingRepository:
    @staticmethod
    async def create(payment_data: dict):
        """Create a new payment incoming in the database."""
        try:
            # Set default values if not provided
            payment_data.setdefault("createdAt", datetime.now())
            payment_data.setdefault("isDelete", False)
            payment_data.setdefault("isApprove", False)
            
            query = insert(payment_incoming_table).values(**payment_data)
            result = await database.execute(query)
            
            log_info(f"Payment incoming created with ID: {result}")
            return {"payment_id": result}
        except Exception as e:
            log_error(f"Error creating payment incoming: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_sales_invoice_id(sales_invoice_id: int):
        """Get all payments associated with a specific sales invoice ID."""
        try:
            log_info(f"Retrieving payments for sales invoice ID: {sales_invoice_id}")
            
            query = select(payment_incoming_table).where(
                payment_incoming_table.c.salesInvoiceID == sales_invoice_id,
                payment_incoming_table.c.isDelete == False
            )
            
            payments = await database.fetch_all(query)
            return [dict(payment) for payment in payments]
        except Exception as e:
            log_error(f"Error getting payments by sales invoice ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_income_id(income_id: int):
        """Get all payments associated with a specific income ID."""
        try:
            log_info(f"Retrieving payments for income ID: {income_id}")
            
            query = select(payment_incoming_table).where(
                payment_incoming_table.c.incomeID == income_id,
                payment_incoming_table.c.isDelete == False
            )
            
            payments = await database.fetch_all(query)
            return [dict(payment) for payment in payments]
        except Exception as e:
            log_error(f"Error getting payments by income ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_calendar_data(month: int, year: int, bank_accounts: Optional[List[int]] = None):
        """Get calendar data for payments incoming."""
        try:
            # Validate input
            if month < 1 or month > 12:
                return {"error": "Invalid month. Month must be between 1 and 12.", "status": 400}
            if year < 2020:
                return {"error": "Invalid year. Year must be 2020 or later.", "status": 400}
            
            # Build query conditions
            conditions = [
                func.extract('month', payment_incoming_table.c.date) == month,
                func.extract('year', payment_incoming_table.c.date) == year,
                payment_incoming_table.c.isDelete == False
            ]
            
            if bank_accounts and len(bank_accounts) > 0:
                conditions.append(payment_incoming_table.c.bankAccountID.in_(bank_accounts))
            
            # Execute query
            query = select(
                func.sum(payment_incoming_table.c.amount).label("amount"),
                payment_incoming_table.c.date
            ).where(*conditions).group_by(payment_incoming_table.c.date)
            
            payments = await database.fetch_all(query)
            
            return [
                {
                    "date": payment.date,
                    "amount": payment.amount
                } for payment in payments
            ]
        except Exception as e:
            log_error(f"Error retrieving calendar data: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_loan_id(loan_id: int):
        """Get all payments associated with a specific loan ID."""
        try:
            log_info(f"Retrieving payments for loan ID: {loan_id}")
            
            query = select(payment_incoming_table).where(
                payment_incoming_table.c.loanID == loan_id,
                payment_incoming_table.c.isDelete == False
            )
            
            payments = await database.fetch_all(query)
            return [dict(payment) for payment in payments]
        except Exception as e:
            log_error(f"Error getting payments by loan ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_id(payment_id: int):
        """Get a payment incoming by its ID."""
        try:
            query = select(payment_incoming_table).where(
                payment_incoming_table.c.id == payment_id,
                payment_incoming_table.c.isDelete == False
            )
            
            payment = await database.fetch_one(query)
            return dict(payment) if payment else None
        except Exception as e:
            log_error(f"Error getting payment by ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update(payment_id: int, update_data: dict):
        """Update a payment incoming."""
        try:
            from sqlalchemy import update
            
            update_data["updatedAt"] = datetime.now()
            
            query = (
                update(payment_incoming_table)
                .where(payment_incoming_table.c.id == payment_id)
                .values(**update_data)
            )
            
            result = await database.execute(query)
            log_info(f"Payment incoming updated: {payment_id}")
            return {"affected_rows": result}
        except Exception as e:
            log_error(f"Error updating payment incoming: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def soft_delete(payment_id: int, user_id: int):
        """Soft delete a payment incoming."""
        try:
            from sqlalchemy import update
            
            query = (
                update(payment_incoming_table)
                .where(payment_incoming_table.c.id == payment_id)
                .values(
                    isDelete=True,
                    updatedBy=user_id,
                    updatedAt=datetime.now()
                )
            )
            
            await database.execute(query)
            log_info(f"Payment incoming soft deleted: {payment_id}")
            return {"message": "Payment deleted successfully"}
        except Exception as e:
            log_error(f"Error soft deleting payment incoming: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_total_by_sales_invoice_id(sales_invoice_id: int):
        """Get total payment amount for a sales invoice."""
        try:
            query = select(
                func.sum(payment_incoming_table.c.amount).label("total_paid")
            ).where(
                payment_incoming_table.c.salesInvoiceID == sales_invoice_id,
                payment_incoming_table.c.isDelete == False
            )
            
            result = await database.fetch_val(query)
            return result or 0
        except Exception as e:
            log_error(f"Error getting total payment by sales invoice ID: {str(e)}")
            return {"error": str(e), "status": 500}