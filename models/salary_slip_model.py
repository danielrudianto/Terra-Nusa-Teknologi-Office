from utils.database import metadata
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, ForeignKey, Float

salary_slips_table = Table(
    "salary_slips",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("userID", Integer, ForeignKey("employee.id"), nullable=False),
    Column("month", Integer, nullable=False),
    Column("year", Integer, nullable=False),
    Column("isPaid", Boolean, default=False, nullable=False),
    Column("basicSalary", Float(), nullable=False),
    Column("transportationAllowanceQuantity", Float(), default=0, nullable=False),
    Column("transportationAllowanceRate", Float(), default=0.0, nullable=False),
    Column("mealAllowanceQuantity", Float(), default=0, nullable=False),
    Column("mealAllowanceRate", Float(), default=0.0, nullable=False),
    Column("overtimeQuantity", Float(), default=0, nullable=False),
    Column("overtimeRate", Float(), default=0.0, nullable=False),
    Column("taxAmount", Float(), default=0.0, nullable=False),
    Column("taxCategory", String(50), nullable=False),
    Column("bankName", String(100), nullable=False),
    Column("bankAccountName", String(100), nullable=False),
    Column("bankAccountNumber", String(100), nullable=False),
    Column("paymentMethod", String(100), nullable=False),
    Column("createdAt", DateTime, nullable=False),
    Column("updatedAt", DateTime, nullable=True),
    Column("createdBy", Integer, nullable=False),
    Column("updatedBy", Integer, nullable=True),
    Column("isDelete", Boolean, default=False, nullable=False),
    Column("deletedAt", DateTime, nullable=True),
    Column("deletedBy", Integer, nullable=True),
    Column("position", String(50), nullable=False),
    Column("department", String(50), nullable=False),
)

salary_slips_allowance_table = Table(
    "salary_slips_allowances",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("salarySlipID", Integer, ForeignKey("salary_slips.id"), nullable=False),
    Column("name", String(100), nullable=False),
    Column("description", String(255), nullable=False),
    Column("amount", Float(), nullable=False),
)

salary_slips_deduction_table = Table(
    "salary_slips_deductions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("salarySlipID", Integer, ForeignKey("salary_slips.id"), nullable=False),
    Column("name", String(100), nullable=False),
    Column("description", String(255), nullable=False),
    Column("amount", Float(), nullable=False),
)