from typing import Annotated
from utils.errors import error_detail
from fastapi import APIRouter, Depends, HTTPException
from utils.auth_utils import get_current_user
from utils.permission import require
from schemas.expense_schema import ExpenseCreate, ExpenseUpdate, ExpenseFilter
from controllers.expense_controller import ExpenseController
from utils.auth_utils import User

router = APIRouter()

@router.post("/")
async def create_expense(expense: ExpenseCreate, current_user: Annotated[User, Depends(require("expenses", "create"))]):
    """
    Create a new expense.
    """
    try:
        userID = current_user.id
        result = await ExpenseController.create_expense(expense.model_dump(), userID)
        if "error" in result:
            raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
        return result
    except HTTPException as e:
        raise e
    
@router.get("/")
async def get_expenses(
    page: int, 
    pageSize: int, 
    filter: int, 
    sortBy: str, 
    sortByDirection: str, 
    keyword: str | None, 
    start: str, 
    end: str, 
    ignore: bool, 
    current_user: Annotated[User, Depends(require("expenses", "read"))],
    isDue: bool = False, 
    isNotDue: bool = False, 
    isPaid: bool = False, 
    isUnpaid: bool = False
):
    """
    Get expenses with pagination and filtering.
    """
    try:
        page = int(page)
        pageSize = int(pageSize)
        filter = int(filter)
        
        if filter == 0:
            filterObject = {
                "isDue": True,
                "isNotDue": True,
                "isPaid": True,
                "isUnpaid": True,
            }
        else:
            filterObject = {
                "isDue": isDue,
                "isNotDue": isNotDue,
                "isPaid": isPaid,
                "isUnpaid": isUnpaid,
            }
            
        result = await ExpenseController.get_expenses(page, pageSize, filterObject, sortBy, sortByDirection, keyword, start, end, ignore)
        if "error" in result:
            raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
        
        return result
    except HTTPException as e:
        raise e

@router.get("/{expense_id}")
async def get_expense_by_id(expense_id: int, current_user: Annotated[User, Depends(require("expenses", "read"))]):
    """
    Get an expense by ID.
    """
    try:
        expense = await ExpenseController.get_expense_by_id(expense_id)
        if "error" in expense:
            raise HTTPException(status_code=expense["status"], detail=expense["error"])
        
        return expense
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{expense_id}")
async def update_expense(expense_id: int, expense: ExpenseUpdate, current_user: Annotated[User, Depends(require("expenses", "update"))]):
    """
    Update an expense.
    """
    try:
        userID = current_user.id
        result = await ExpenseController.update_expense(expense_id, expense.model_dump(exclude_unset=True), userID)
        if "error" in result:
            raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
        return result
    except HTTPException as e:
        raise e

@router.delete("/{expense_id}")
async def delete_expense(expense_id: int, current_user: Annotated[User, Depends(require("expenses", "delete"))]):
    """
    Delete an expense.
    """
    try:
        userID = current_user.id
        result = await ExpenseController.delete_expense(expense_id, userID)
        if "error" in result:
            raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
        return result
    except HTTPException as e:
        raise e

@router.put("/{expense_id}/approve")
async def approve_expense_by_id(expense_id: int, current_user: Annotated[User, Depends(require("expenses", "approve"))]):
    """
    Approve an expense by ID.
    """
    userID = current_user.id
    result = await ExpenseController.approve_expense_by_id(expense_id, userID)
    if "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result

@router.get("/{expense_id}/payments")
async def get_payments_by_expense_id(
    expense_id: int,
    # Balikannya memuat nama dan nomor rekening pembayar, bukan sekadar
    # nominalnya — sehingga dijaga seperti data pembayaran.
    current_user: Annotated[User, Depends(require("payment_outgoing", "read"))],
):
    """
    Get payments by expense ID.
    """
    expense = await ExpenseController.get_expense_by_id(expense_id)
    
    return expense

@router.patch("/{expense_id}/payment-status")
async def update_payment_status(expense_id: int, isPaid: bool, current_user: Annotated[User, Depends(require("expenses", "update"))]):
    """
    Update payment status of an expense.
    """
    try:
        userID = current_user.id
        result = await ExpenseController.update_payment_status(expense_id, isPaid, userID)
        if "error" in result:
            raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
        return result
    except HTTPException as e:
        raise e