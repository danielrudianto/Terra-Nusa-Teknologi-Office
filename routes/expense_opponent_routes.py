from typing import Annotated
from utils.errors import error_detail
from fastapi import APIRouter, Depends, HTTPException
from utils.auth_utils import get_current_user
from utils.permission import require
from schemas.expense_opponent_schema import ExpenseOpponentCreate, ExpenseOpponentUpdate
from controllers.expense_opponent_controller import ExpenseOpponentController
from utils.auth_utils import User

router = APIRouter()

@router.post("/")
async def create_expense_opponent(
    expense_opponent: ExpenseOpponentCreate, 
    current_user: Annotated[User, Depends(require("expense_opponent", "create"))]
):
    """
    Create a new expense opponent.
    """
    try:
        userID = current_user.id
        result = await ExpenseOpponentController.create_expense_opponent(expense_opponent.model_dump(), userID)
        if "error" in result:
            raise HTTPException(status_code=500, detail="Internal server error")
        return result
    except HTTPException as e:
        raise e
    
@router.get("/")
async def get_expense_opponents(
    page: int, 
    pageSize: int, 
    sortBy: str | None, 
    sortByDirection: str, 
    keyword: str, 
    current_user: Annotated[User, Depends(require("expense_opponent", "read"))]
):
    """
    Get expense opponents with pagination and filtering.
    """
    try:
        page = int(page)
        pageSize = int(pageSize)

        result = await ExpenseOpponentController.get_expense_opponents(page, pageSize, sortBy, sortByDirection, keyword)
        if "error" in result:
            raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
        
        return result
    except HTTPException as e:
        raise e

@router.get("/{opponent_id}")
async def get_expense_opponent_by_id(
    opponent_id: int, 
    current_user: Annotated[User, Depends(require("expense_opponent", "read"))]
):
    """
    Get an expense opponent by ID.
    """
    try:
        result = await ExpenseOpponentController.get_expense_opponent_by_id(opponent_id)
        if "error" in result:
            raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
        return result
    except HTTPException as e:
        raise e

@router.put("/{opponent_id}")
async def update_expense_opponent(
    opponent_id: int, 
    expense_opponent: ExpenseOpponentUpdate, 
    current_user: Annotated[User, Depends(require("expense_opponent", "update"))]
):
    """
    Update an expense opponent.
    """
    try:
        userID = current_user.id
        result = await ExpenseOpponentController.update_expense_opponent(
            opponent_id, 
            expense_opponent.model_dump(exclude_unset=True), 
            userID
        )
        if "error" in result:
            raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
        return result
    except HTTPException as e:
        raise e

@router.delete("/{opponent_id}")
async def delete_expense_opponent(
    opponent_id: int, 
    current_user: Annotated[User, Depends(require("expense_opponent", "delete"))]
):
    """
    Delete an expense opponent.
    """
    try:
        userID = current_user.id
        result = await ExpenseOpponentController.delete_expense_opponent(opponent_id, userID)
        if "error" in result:
            raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
        return result
    except HTTPException as e:
        raise e

@router.get("/search/{keyword}")
async def search_expense_opponents(
    keyword: str,
    limit: int,
    current_user: Annotated[User, Depends(require("expense_opponent", "read"))]
):
    """
    Search expense opponents by name.
    """
    try:
        result = await ExpenseOpponentController.search_expense_opponents(keyword, limit)
        if "error" in result:
            raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
        return result
    except HTTPException as e:
        raise e