from fastapi import APIRouter, Depends, HTTPException, Query
from utils.auth_utils import get_current_user
from utils.logger_utils import log_error
from typing import Annotated, Optional
from controllers.sales_invoice_controller import SalesInvoiceController
from schemas.sales_invoice_schema import SalesInvoiceCreate
from utils.auth_utils import get_current_user
from typing import Annotated

router = APIRouter()

@router.post("/")
async def create_sales_invoice(
    sales_invoice: SalesInvoiceCreate, 
    current_user: Annotated[dict, Depends(get_current_user)]
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
    current_user: Annotated[dict, Depends(get_current_user)],
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
    current_user: Annotated[dict, Depends(get_current_user)]
):
    """
    Get sales invoice by ID.
    """
    result = await SalesInvoiceController.get_sales_invoice_by_id(sales_invoice_id)
    return result

@router.get("/")
async def get_sales_invoices(
    current_user: Annotated[dict, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
    sortBy: str = Query("date"),
    sortByDirection: str = Query("desc", regex="^(asc|desc)$"),
    keyword: Optional[str] = Query(None),
):
    """
    Get sales invoices with pagination.
    """
    result = await SalesInvoiceController.get_sales_invoices(
        page, pageSize, sortBy, sortByDirection, keyword
    )
    return result

@router.put("/reject/{sales_invoice_id}")
async def reject_sales_invoice(
    sales_invoice_id: int,
    current_user: Annotated[dict, Depends(get_current_user)]
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
    current_user: Annotated[dict, Depends(get_current_user)]
):
    """
    Approve sales invoice by ID.
    """
    user_id = current_user["id"]
    tax_invoice_name = data.get("taxInvoiceName")
    result = await SalesInvoiceController.approve_sales_invoice(
        sales_invoice_id, tax_invoice_name, user_id
    )
    return result