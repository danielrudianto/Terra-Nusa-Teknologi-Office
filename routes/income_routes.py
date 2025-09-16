from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from utils.auth_utils import get_current_user
from models.user_model import User
from utils.logger_utils import log_error
from controllers.income_controller import IncomeController
from controllers.payment_incoming_controller import PaymentIncomingController

router = APIRouter()

@router.post("/")
async def create_income(income_data: dict, user: Annotated[User, Depends(get_current_user)]):
    """
    Create a new interpayment. Requires a valid token.
    """
    userID = user["id"]
    paymentDate = income_data.pop("paymentDate")
    bankAccountID = income_data.pop("bankAccountID")
    
    result = await IncomeController.create_income(income_data, userID)
    if "error" in result:
        log_error(f"Error creating interpayment: {result['error']}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    payment = await PaymentIncomingController.create_payment({
        "bankAccountID": bankAccountID,
        "date": paymentDate,
        "incomeID": result['incomeID'],
        "salesInvoiceID": None,
        "loanID": None,
        "amount": income_data['amount']
    }, userID) 
    
    if "error" in payment:
        log_error(f"Error creating incoming payment: {payment['error']}")
        raise HTTPException(status_code=payment["status"], detail=payment["error"])
    
    return result

@router.get("/")
async def fetch_income(page: int, pageSize: int, sortBy: str, sortByDirection: str, keyword: str | None, user: Annotated[User, Depends(get_current_user)]):
    try:
        page = int(page)
        pageSize = int(pageSize)
        
        result = await IncomeController.get_income(page, pageSize, sortBy, sortByDirection, keyword)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        
        return result
    except HTTPException as e:
        raise e
