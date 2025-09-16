from fastapi import APIRouter, Depends
from utils.auth_utils import get_current_user
from fastapi import HTTPException
from utils.logger_utils import log_error
from typing import Annotated
from utils.auth_utils import User
from controllers.sales_invoice_controller import SalesInvoiceController
from models.sales_invoice_model import SalesInvoice

router = APIRouter()

@router.post("/")
async def create_sales_invoice(sales_invoice: SalesInvoice, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Create a new sales invoice. Requires a valid token.
    """
    userID = current_user["id"]
    result = await SalesInvoiceController.create_sales_invoice(sales_invoice.model_dump(), userID)
    if "error" in result:
        log_error(f"Error creating sales invoice: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result

@router.get("/exists")
async def check_sales_invoice(description: str, projectName: str, clientID: int, name: str, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Check if a sales invoice with the same description, project name, and client ID already exists.
    Requires a valid token.
    """
    result = await SalesInvoiceController.check_sales_invoice(description, projectName, clientID, name)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result

@router.get("/{salesInvoiceID}")
async def get_sales_invoice_by_id(salesInvoiceID: int, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Get sales invoice by salesInvoiceID
    """
    result = await SalesInvoiceController.get_sales_invoice_by_id(salesInvoiceID)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result

@router.get("/")
async def get_sales_invoices(page: int, pageSize: int, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Get sales invoices with pagination. Requires a valid token.
    """
    result = await SalesInvoiceController.get_sales_invoices(page, pageSize)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result

@router.put("/reject/{salesInvoiceID}")
async def reject_sales_invoice(salesInvoiceID: int, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Reject sales invoice by ID.
    """
    userID = current_user["id"]
    result = await SalesInvoiceController.reject_sales_invoice_by_id(salesInvoiceID, userID)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result

@router.put("/approve/{salesInvoiceID}")
async def reject_sales_invoice(salesInvoiceID: int, data: dict, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Approve sales invoice by ID.
    """
    userID = current_user["id"]
    taxInvoiceName = data["taxInvoiceName"]
    result = await SalesInvoiceController.approve_sales_invoice_by_id(salesInvoiceID, taxInvoiceName, userID)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result