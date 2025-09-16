from pydantic import BaseModel, Field
from typing import List
from sqlalchemy import Table, Column, DateTime, Integer, String, Boolean, ForeignKey, Date, or_, select, func, and_, case, literal
from utils.database import metadata, database
from datetime import date as d, datetime as dt
from models.purchase_model import purchases_table
from models.reimbursement_model import reimbursements_table
from models.salary_slip_model import salary_slips_table
from models.employee_model import employees_table
from models.expense_model import expenses_table, expense_opponents_table
from models.supplier_model import suppliers_table
from utils.logger_utils import log_error, log_info


class PaymentIncoming(BaseModel):
    date: d #Payment date
    amount: float #Payment amount
    incomeID: int | None = None #Income ID
    salesInvoiceID: int | None = None #Sales invoice ID
    loanID: int | None = None #Loan ID
    bankAccountID: int | None = None #Bank account ID
    isApprove: bool = False #Whether the payment is approved
    isDelete: bool = False #Whether the payment is deleted
    createdAt: dt = Field(default_factory=dt.now) #Creation date and time
    createdBy: int | None = None #ID of the user who created the payment
    updatedBy: int | None = None #ID of the user who approved the payment
    updatedAt: dt | None = None #Last update date and time

    # Constructor
    def __init__(self, **data):
        super().__init__(**data)
        self.createdAt = data.get("createdAt", dt.now())
        self.updatedAt = data.get("updatedAt", None)
        self.isDelete = data.get("isDelete", False)
        self.isApprove = data.get("isApprove", False)

    # Create
    @staticmethod
    async def create(payment_data: dict):
        """
        Create a new payment in the database.
        
        Returns:
            dict: A success message with the created payment ID.
        """
        try:
            query = payments_incoming_table.insert().values(payment_data)
            result = await database.execute(query)
            return {"message": "Payment created successfully", "payment_id": result}
        except Exception as e:
            log_error(f"Error creating payment: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_payments_by_sales_invoice_id(salesInvoiceID: int):
        """
        Get all payments associated with a specific sales invoice ID.
        
        Args:
            purchaseID (int): The ID of the purchase.
        
        Returns:
            list: A list of payments associated with the purchase.
        """
        log_info(f"Retrieving payments for sales invoice ID: {salesInvoiceID}")
        query = select(payments_incoming_table).where(
            payments_incoming_table.c.salesInvoiceID == salesInvoiceID,
            payments_incoming_table.c.isDelete == False
        )
        
        payments = await database.fetch_all(query)
        
        return [PaymentIncoming(**payment) for payment in payments]
    
# Define the payments table
payments_incoming_table = Table(
    "payment_incoming",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date", Date(), nullable=False),
    Column("amount", Integer, nullable=False),
    Column("salesInvoiceID", Integer, ForeignKey("purchases.id"), nullable=True),
    Column("incomeID", Integer, ForeignKey('income.id'), nullable=True),
    Column("loanID", Integer, ForeignKey('loans.id'), nullable=True),
    Column("bankAccountID", Integer, ForeignKey("bank_accounts.id"), nullable=True),
    Column("createdAt", DateTime(), nullable=False, default=dt.now()),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True, default=None,),
    Column("isDelete", Boolean, default=False),
    Column("isApprove", Boolean, default=False),
)
