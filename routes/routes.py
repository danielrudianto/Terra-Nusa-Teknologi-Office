from fastapi import APIRouter

from routes.client_routes import router as client_router
from routes.auth_routes import router as auth_router
from routes.supplier_routes import router as supplier_router
from routes.purchase_routes import router as purchase_router
from routes.reimbursement_routes import router as reimbursement_router
from routes.bank_routes import router as bank_router
from routes.expenses_routes import router as expenses_router
from routes.payment_routes import router as payment_router
from routes.employees_routes import router as employees_router
from routes.expense_opponent_routes import router as expense_opponent_router
from routes.salary_slip_routes import router as salary_slip_router
from routes.calendar_routes import router as calendar_router
from routes.interpayment_routes import router as interpayment_router
from routes.sales_invoice_routes import router as sales_invoice_router
from routes.asset_routes import router as asset_router
from routes.tax_routes import router as tax_router
from routes.purchase_draft_routes import router as purchase_draft_router

# Create a router instance
router = APIRouter()

# Include client routes
router.include_router(client_router, prefix="/clients", tags=["Clients"])
router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(supplier_router, prefix="/suppliers", tags=["Suppliers"])
router.include_router(purchase_router, prefix="/purchases", tags=["Purchases"])
router.include_router(reimbursement_router, prefix="/reimbursements", tags=["Reimbursements"])
router.include_router(bank_router, prefix="/banks", tags=["Banks"])
router.include_router(expenses_router, prefix="/expenses", tags=["Expenses"])
router.include_router(payment_router, prefix="/payments", tags=["Payments"])
router.include_router(employees_router, prefix="/employees", tags=["Employees"])
router.include_router(expense_opponent_router, prefix="/expense-opponents", tags=["Expense Opponents"])
router.include_router(salary_slip_router, prefix="/salary-slips", tags=["Salary Slips"])
router.include_router(calendar_router, prefix="/calendar", tags=["Calendar"])
router.include_router(interpayment_router, prefix="/interpayments", tags=["Interpayments"])
router.include_router(sales_invoice_router, prefix="/sales-invoices", tags=["Sales Invoices"])
router.include_router(asset_router, prefix="/assets", tags=["Assets"])
router.include_router(tax_router, prefix="/taxes", tags=["Taxes"])
router.include_router(purchase_draft_router, prefix="/purchase-draft", tags=["Purchase draft"])