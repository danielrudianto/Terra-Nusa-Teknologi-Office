from pydantic import BaseModel, Field
from sqlalchemy import Table, Column, DateTime, Integer, String, Boolean, ForeignKey, Date
from utils.database import metadata
from datetime import date as d, datetime as dt


# Pydantic model (request body / typed payment object)
class PaymentOutgoing(BaseModel):
    date: d #Payment date
    amount: float #Payment amount
    purchaseID: int | None = None #Purchase ID
    expenseID: int | None = None #Expense ID
    reimbursementID: int | None = None #Reimbursement ID
    salarySlipID: int | None = None #Salary Slip ID
    loanID: int | None = None
    bankAccountID: int | None = None #Bank account ID
    isApprove: bool = False #Whether the payment is approved
    isDelete: bool = False #Whether the payment is deleted
    createdAt: dt = Field(default_factory=dt.now) #Creation date and time
    createdBy: int | None = None #ID of the user who created the payment
    updatedBy: int | None = None #ID of the user who approved the payment
    updatedAt: dt | None = None #Last update date and time
    status: str = "ready" #Document status when it was created

    # Constructor
    def __init__(self, **data):
        super().__init__(**data)
        self.createdAt = data.get("createdAt", dt.now())
        self.updatedAt = data.get("updatedAt", None)
        self.isDelete = data.get("isDelete", False)
        self.isApprove = data.get("isApprove", False)
        self.status = data.get("status", "ready")

    # Create


# Define the payments table
payments_outgoing_table = Table(
    "payment_outgoing",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date", Date(), nullable=False),
    Column("amount", Integer, nullable=False),
    Column("purchaseID", Integer, ForeignKey("purchases.id"), nullable=True),
    Column("expenseID", Integer, ForeignKey('expenses.id'), nullable=True),
    Column("reimbursementID", Integer, ForeignKey('reimbursements.id'), nullable=True),
    Column("salarySlipID", Integer, ForeignKey('salary_slips.id'), nullable=True),
    Column("loanID", Integer, ForeignKey("loans.id"), nullable=True),
    Column("bankAccountID", Integer, ForeignKey("bank_accounts.id"), nullable=True),
    Column("createdAt", DateTime(), nullable=False, default=dt.now()),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True, default=None,),
    Column("isDelete", Boolean, default=False),
    Column("isApprove", Boolean, default=False),
    Column("status", String(50), default="ready", nullable=False, comment="Document status when it was created")
)