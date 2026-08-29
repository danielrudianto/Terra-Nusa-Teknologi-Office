from fastapi import APIRouter, Depends, HTTPException, Query
from utils.auth_utils import get_current_user
from utils.permission import require
from utils.logger_utils import log_error
from typing import Annotated, Optional, List
from controllers.sales_invoice_controller import SalesInvoiceController
from schemas.sales_invoice_schema import SalesInvoiceCreate, SalesInvoiceTaxInvoiceUpdate, SalesInvoiceIncomeTaxUpdate
from utils.auth_utils import get_current_user
from typing import Annotated
from utils.auth_utils import User

router = APIRouter()

@router.post("/")
async def create_sales_invoice(
    sales_invoice: SalesInvoiceCreate, 
    current_user: Annotated[User, Depends(require("sales_invoice", "create"))]
):
    """
    Create a new sales invoice.
    """
    user_id = current_user["id"]
    result = await SalesInvoiceController.create_sales_invoice(
        sales_invoice.model_dump(), user_id
    )
    return result

@router.get("/exists")
async def check_sales_invoice(
    current_user: Annotated[User, Depends(require("sales_invoice", "read"))],
    description: str = Query(...),
    projectName: str = Query(...),
    clientID: int = Query(...),
    name: str = Query(...),
):
    """
    Check if a sales invoice with the same description, project name, and client ID already exists.
    """
    result = await SalesInvoiceController.check_sales_invoice(
        description, projectName, clientID, name
    )
    return result

@router.get("/{sales_invoice_id}")
async def get_sales_invoice_by_id(
    sales_invoice_id: int,
    current_user: Annotated[User, Depends(require("sales_invoice", "read"))]
):
    """
    Get sales invoice by ID.
    """
    result = await SalesInvoiceController.get_sales_invoice_by_id(sales_invoice_id)
    return result

@router.get("/")
async def get_sales_invoices(
    current_user: Annotated[User, Depends(require("sales_invoice", "read"))],
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
    sortBy: str = Query("date"),
    sortByDirection: str = Query("desc", regex="^(asc|desc)$"),
    keyword: Optional[str] = Query(None),
    filters: Optional[List[str]] = Query(None),
):
    """
    Get sales invoices with pagination.
    filters: paid, unpaid, complete, no_tax_invoice, no_withholding (multi-select).
    """
    result = await SalesInvoiceController.get_sales_invoices(
        page, pageSize, sortBy, sortByDirection, keyword, filters
    )
    return result

@router.put("/reject/{sales_invoice_id}")
async def reject_sales_invoice(
    sales_invoice_id: int,
    current_user: Annotated[User, Depends(require("sales_invoice", "approve"))]
):
    """
    Reject sales invoice by ID.
    """
    user_id = current_user["id"]
    result = await SalesInvoiceController.reject_sales_invoice(sales_invoice_id, user_id)
    return result

@router.put("/approve/{sales_invoice_id}")
async def approve_sales_invoice(
    sales_invoice_id: int,
    data: dict,
    current_user: Annotated[User, Depends(require("sales_invoice", "approve"))]
):
    """
    Approve sales invoice by ID.
    """
    user_id = current_user["id"]
    tax_invoice_name = data.get("taxInvoiceName")
    result = await SalesInvoiceController.approve_sales_invoice(
        sales_invoice_id, tax_invoice_name, user_id, int(current_user["authenticationLevel"] or 1))
    return result

@router.put("/tax-invoice/{sales_invoice_id}")
async def set_tax_invoice_name(
    sales_invoice_id: int,
    data: SalesInvoiceTaxInvoiceUpdate,
    current_user: Annotated[User, Depends(require("sales_invoice", "update"))]
):
    """Set nomor faktur pajak PPN pada sales invoice, beserta masa pajaknya.

    `taxPeriod` boleh kosong — kosong berarti fakturnya dilaporkan pada masa
    tanggal invoicenya sendiri.
    """
    user_id = current_user["id"]
    return await SalesInvoiceController.set_tax_invoice_name(
        sales_invoice_id,
        data.taxInvoiceName,
        user_id,
        data.taxPeriod,
        int(current_user["authenticationLevel"] or 1),
    )


@router.put("/income-tax/{sales_invoice_id}")
async def set_income_tax_name(
    sales_invoice_id: int,
    data: SalesInvoiceIncomeTaxUpdate,
    current_user: Annotated[User, Depends(require("sales_invoice", "update"))]
):
    """Set nomor bukti potong PPh pada sales invoice (hanya yang sudah dibayar & ada PPh).

    Mengisi pertama kali bebas seperti biasa; MENGUBAH yang sudah terisi hanya
    boleh level 5 — dijaga di lapisan repository, bukan sekadar di layar.
    """
    user_id = current_user["id"]
    return await SalesInvoiceController.set_income_tax_name(
        sales_invoice_id,
        data.incomeTaxInvoiceName,
        user_id,
        int(current_user["authenticationLevel"] or 1),
    )