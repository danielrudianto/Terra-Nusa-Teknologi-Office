from pydantic import BaseModel, Field
from typing import List
from sqlalchemy import Table, Column, DateTime, Integer, String, Boolean, ForeignKey, Date, or_, select, func, and_, case, literal
from utils.database import metadata, database
from datetime import date as d, datetime as dt
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
        self.isApprove = data.get("isApprove", True)

    # Create
    async def create(self):
        """
        Create a new payment in the database.
        
        Returns:
            dict: A success message with the created payment ID.
        """
        try:
            query = payments_incoming_table.insert().values(
                date=self.date,
                amount=self.amount,
                salesInvoiceID=self.salesInvoiceID,
                incomeID=self.incomeID,
                loanID=self.loanID,
                bankAccountID=self.bankAccountID,
                createdAt=self.createdAt,
                createdBy=self.createdBy,
                updatedAt=self.updatedAt,
                updatedBy=self.updatedBy,
                isDelete=self.isDelete,
                isApprove=self.isApprove,
            )
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
    
    @staticmethod
    async def get_payments_by_income_id(incomeID: int):
        """
        Get all payments associated with a specific sales invoice ID.
        
        Args:
            purchaseID (int): The ID of the purchase.
        
        Returns:
            list: A list of payments associated with the purchase.
        """
        log_info(f"Retrieving payments for income ID: {incomeID}")
        query = select(payments_incoming_table).where(
            payments_incoming_table.c.incomeID == incomeID,
            payments_incoming_table.c.isDelete == False
        )
        
        payments = await database.fetch_all(query)
        
        return [PaymentIncoming(**payment) for payment in payments]

    @staticmethod
    async def get_calendar_data(month: int, year: int, bankAccounts: List[int]):
        try:
            if month < 1 or month > 12:
                return {"error": "Invalid month. Month must be between 1 and 12.", "status": 400}
            if year < 2020:
                return {"error": "Invalid year. Year must be 2020 or later.", "status": 400}
            
            if(bankAccounts is not None and len(bankAccounts) > 0):
                query = select(
                    func.sum(payments_incoming_table.c.amount).label("amount"),
                    payments_incoming_table.c.date
                ).where(
                    func.extract('month', payments_incoming_table.c.date) == month,
                    func.extract('year', payments_incoming_table.c.date) == year,
                    payments_incoming_table.c.isDelete == False,
                    payments_incoming_table.c.bankAccountID.in_(bankAccounts)
                ).group_by(
                    payments_incoming_table.c.date
                )
            else:
                # If no bank accounts are provided, fetch all payments for the specified month and year
                query = select(
                    func.sum(payments_incoming_table.c.amount).label("amount"),
                    payments_incoming_table.c.date
                ).where(
                    func.extract('month', payments_incoming_table.c.date) == month,
                    func.extract('year', payments_incoming_table.c.date) == year,
                    payments_incoming_table.c.isDelete == False
                ).group_by(
                    payments_incoming_table.c.date
                )
                
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
