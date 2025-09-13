from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from utils.auth_utils import get_current_user
from models.user_model import User
from models.expense_model import Expense
from controllers.expense_controller import ExpenseController

router = APIRouter()

@router.post("/")
async def create_expense(expense: Expense, current_user: Annotated[User, Depends(get_current_user)]):
    try:
        userID = current_user["id"]
        result = await ExpenseController.create_expense(expense.model_dump(), userID)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        raise e
    
@router.get("/")
async def get_expenses(page: int, pageSize: int, filter: int, sortBy: str, sortByDirection: str, keyword: str | None, current_user: Annotated[User, Depends(get_current_user)], isDue: bool = False, isNotDue: bool = False, isPaid: bool = False, isUnpaid: bool = False, isDraft: bool = False, isReady: bool = False):
    try:
        page = int(page)
        pageSize = int(pageSize)
        filter = int(filter)
        filterObject = {}

        if(filter == 0):
            filterObject = {
                "isDue": True,
                "isNotDue": True,
                "isPaid": True,
                "isUnpaid": True,
                "isDraft": True,
                "isReady": True
            }
        else :
            filterObject = {
                "isDue": isDue,
                "isNotDue": isNotDue,
                "isPaid": isPaid,
                "isUnpaid": isUnpaid,
                "isDraft": isDraft,
                "isReady": isReady
            }
        result = await ExpenseController.get_expenses(page, pageSize, filterObject, sortBy, sortByDirection, keyword)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        
        return result
    except HTTPException as e:
        raise e

@router.put("/approve")
async def approve_expense_by_id(expense_id: int, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Approve payments by ID. Requires a valid token.
    """
    userID = current_user["id"]
    expense = await ExpenseController.approve_expense_by_id(expense_id, userID)
    if expense is None:
        raise 

@router.get("/payments/{purchase_id}")
async def get_payments_by_purchase_id(purchase_id: int, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Get payments by purchase ID. Requires a valid token.
    """
    expense = await ExpenseController.get_expense_by_id(purchase_id)
    result = await ExpenseController.get_payments_by_expense_id(purchase_id)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return {
        "expense": expense,
        "payments": result
    }