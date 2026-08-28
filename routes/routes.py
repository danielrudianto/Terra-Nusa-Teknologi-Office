from fastapi import APIRouter

from routes.client_routes import router as client_router
from routes.auth_routes import router as auth_router
from routes.permission_routes import router as permission_router
from routes.user_access_routes import router as user_access_router
from routes.supplier_routes import router as supplier_router
from routes.purchase_routes import router as purchase_router
from routes.reimbursement_routes import router as reimbursement_router
from routes.bank_routes import router as bank_router
from routes.expenses_routes import router as expenses_router
from routes.payment_outgoing_routes import router as payment_outgoing_router
from routes.payment_incoming_routes import router as payment_incoming_router
from routes.employees_routes import router as employees_router
from routes.employee_profile_routes import router as employee_profile_router
from routes.employee_form_routes import router as employee_form_router
from routes.hr_recruitment_routes import router as hr_recruitment_router
from routes.expense_opponent_routes import router as expense_opponent_router
from routes.salary_slip_routes import router as salary_slip_router
from routes.calendar_routes import router as calendar_router
from routes.interpayment_routes import router as interpayment_router
from routes.sales_invoice_routes import router as sales_invoice_router
from routes.asset_routes import router as asset_router
from routes.tax_routes import router as tax_router
from routes.purchase_draft_routes import router as purchase_draft_router
from routes.income_routes import router as income_router
from routes.loan_routes import router as loan_router
from routes.purchase_order_routes import router as purchase_order_router
from routes.certificate_of_payment_routes import router as certificate_of_payment_router
from routes.dashboard_routes import router as dashboard_router
from routes.master_item_routes import router as master_item_router
from routes.master_equipment_routes import router as master_equipment_router
from routes.user_routes import router as user_router
from routes.agenda_routes import router as agenda_router
from routes.project_routes import router as project_router
from routes.tender_routes import router as tender_router
from routes.payment_plan_routes import router as payment_plan_router
from routes.finance_status_routes import router as finance_status_router
from routes.user_avatar_routes import router as user_avatar_router
from routes.audit_log_routes import router as audit_log_router
from routes.push_routes import router as push_router
from routes.report_routes import router as report_router

# Create a router instance
router = APIRouter()

# Include client routes
router.include_router(client_router, prefix="/clients", tags=["Clients"])
router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(permission_router, prefix="/permissions", tags=["Permissions"])
router.include_router(user_access_router, prefix="/user-access", tags=["User access"])
router.include_router(supplier_router, prefix="/suppliers", tags=["Suppliers"])
router.include_router(tender_router, prefix="/tenders", tags=["Tenders"])
router.include_router(payment_plan_router, prefix="/payment-plans", tags=["Payment plans"])
router.include_router(purchase_router, prefix="/purchases", tags=["Purchases"])
router.include_router(reimbursement_router, prefix="/reimbursements", tags=["Reimbursements"])
router.include_router(bank_router, prefix="/banks", tags=["Banks"])
router.include_router(expenses_router, prefix="/expenses", tags=["Expenses"])
router.include_router(payment_outgoing_router, prefix="/outgoing-payments", tags=["Outgoing payments"])
router.include_router(payment_incoming_router, prefix="/incoming-payments", tags=["Incoming Payments"])
router.include_router(employees_router, prefix="/employees", tags=["Employees"])
# Awalan terpisah dari /employees: izinnya berbeda modul, dan
# menempelkannya sebagai sub-rute membuat penjaganya mudah tertukar.
router.include_router(
    employee_profile_router,
    prefix="/employee-profiles",
    tags=["Employee profiles"],
)
router.include_router(
    employee_form_router,
    prefix="/employee-forms",
    tags=["Employee forms"],
)
# Awalan terpisah dari /employees: pelamar BUKAN karyawan, dan menempelkannya
# sebagai sub-rute membuat penjaga izinnya mudah tertukar.
router.include_router(
    hr_recruitment_router,
    prefix="/hr",
    tags=["HR recruitment"],
)
router.include_router(expense_opponent_router, prefix="/expense-opponents", tags=["Expense Opponents"])
router.include_router(salary_slip_router, prefix="/salary-slips", tags=["Salary Slips"])
router.include_router(calendar_router, prefix="/calendar", tags=["Calendar"])
router.include_router(interpayment_router, prefix="/interpayments", tags=["Interpayments"])
router.include_router(sales_invoice_router, prefix="/sales-invoices", tags=["Sales Invoices"])
router.include_router(asset_router, prefix="/assets", tags=["Assets"])
router.include_router(tax_router, prefix="/taxes", tags=["Taxes"])
router.include_router(purchase_draft_router, prefix="/purchase-draft", tags=["Purchase draft"])
router.include_router(income_router, prefix="/income", tags=["Income"])
router.include_router(user_router, prefix="/users", tags=["Users"])
router.include_router(agenda_router, prefix="/agenda", tags=["Agenda"])
router.include_router(project_router, prefix="/projects", tags=["Projects"])
router.include_router(finance_status_router, prefix="/finance-status", tags=["Finance Status"])
router.include_router(loan_router, prefix="/loans", tags=["Loan"])
router.include_router(purchase_order_router, prefix="/purchase-orders", tags=["Purchase Orders"])
router.include_router(
    certificate_of_payment_router,
    prefix="/certificate-of-payments",
    tags=["Certificate of Payment"],
)
router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
router.include_router(master_item_router, prefix="/master-items", tags=["Master Items"])
router.include_router(master_equipment_router, prefix="/master-equipment", tags=["Master Equipment"])
router.include_router(user_avatar_router, prefix="/user-avatars", tags=["User Avatars"])
router.include_router(audit_log_router, prefix="/audit-logs", tags=["Audit Logs"])
router.include_router(push_router, prefix="/push", tags=["Push Notifications"])
router.include_router(report_router, prefix="/reports", tags=["Reports"])