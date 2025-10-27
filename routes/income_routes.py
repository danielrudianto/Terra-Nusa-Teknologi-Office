from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from utils.auth_utils import get_current_user
from utils.logger_utils import log_error
from controllers.income_controller import IncomeController
from controllers.payment_incoming_controller import PaymentIncomingController
from utils.auth_utils import User

router = APIRouter()

@router.post("/")
async def create_income(income_data: dict, user: Annotated[User, Depends(get_current_user)]):
    """
    Create a new income. Requires a valid token.
    """
    userID = user.id
    paymentDate = income_data.pop("paymentDate")
    bankAccountID = income_data.pop("bankAccountID")
    
    result = await IncomeController.create_income(income_data, userID)
    if "error" in result:
        log_error(f"Error creating income: {result['error']}")
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
async def fetch_income(
    page: int, 
    pageSize: int, 
    start: str,
    end: str,
    sortBy: str, 
    sortByDirection: str, 
    keyword: str | None, 
    ignore: bool,
    user: Annotated[User, Depends(get_current_user)]
):
    """
    Get incomes with pagination and filtering.
    """
    try:
        page = int(page)
        pageSize = int(pageSize)
        
        result = await IncomeController.get_income(page, pageSize, sortBy, start, end, sortByDirection, keyword, ignore)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        
        return result
    except HTTPException as e:
        raise e

@router.get("/{income_id}")
async def get_income(income_id: int, user: Annotated[User, Depends(get_current_user)]):
    """
    Get a single income by ID.
    """
    try:
        result = await IncomeController.get_income_by_id(income_id)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        
        return result
    except HTTPException as e:
        raise e

@router.put("/{income_id}")
async def update_income(
    income_id: int, 
    income_data: dict, 
    user: Annotated[User, Depends(get_current_user)]
):
    """
    Update an income.
    """
    try:
        userID = user.id
        result = await IncomeController.update_income(income_id, income_data, userID)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        
        return result
    except HTTPException as e:
        raise e

@router.delete("/{income_id}")
async def delete_income(income_id: int, user: Annotated[User, Depends(get_current_user)]):
    """
    Delete an income.
    """
    try:
        userID = user.id
        result = await IncomeController.delete_income(income_id, userID)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        
        return result
    except HTTPException as e:
        raise e