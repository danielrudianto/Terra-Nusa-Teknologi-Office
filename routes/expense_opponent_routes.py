from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from utils.auth_utils import get_current_user
from models.user_model import User
from controllers.expense_opponent_controller import ExpenseOpponentController
from models.expense_opponent_model import ExpenseOpponent

router = APIRouter()

@router.post("/")
async def create_expense_opponent(expense_opponent: ExpenseOpponent, current_user: Annotated[User, Depends(get_current_user)]):
    try:
        userID = current_user["id"]
        result = await ExpenseOpponentController.create_expense_opponent(expense_opponent.model_dump(), userID)
        if "error" in result:
            raise HTTPException(status_code=500, detail="Internal server error")
        return result
    except HTTPException as e:
        raise e
    
@router.get("/")
async def get_expense_opponents(page: int, pageSize: int, sortBy: str | None, sortByDirection: str | None, keyword: str | None, current_user: Annotated[User, Depends(get_current_user)]):
    try:
        page = int(page)
        pageSize = int(pageSize)

        result = await ExpenseOpponentController.get_expense_opponents(page, pageSize, sortBy, sortByDirection, keyword)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        
        return result
    except HTTPException as e:
        raise e