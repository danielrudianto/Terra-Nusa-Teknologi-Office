from fastapi import APIRouter, Depends
from utils.auth_utils import get_current_user
from fastapi import HTTPException
from utils.logger_utils import log_error
from typing import Annotated
from utils.auth_utils import User
from models.sales_invoice_model import SalesInvoice

router = APIRouter()

@router.post("/")
async def create_sales_invoice(sales_invoice: SalesInvoice, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Create a new sales invoice. Requires a valid token.
    """
    userID = current_user["id"]
    result = await SalesInvoice.create_sales_invoice(sales_invoice.model_dump(), userID)
    if "error" in result:
        log_error(f"Error creating sales invoice: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result