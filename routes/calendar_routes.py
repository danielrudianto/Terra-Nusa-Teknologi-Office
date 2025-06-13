from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from controllers.payment_controller import PaymentController
from models.bank_model import BankAccount
from utils.auth_utils import get_current_user
from models.user_model import User

router = APIRouter()

@router.get("/")
async def get_calendar_data(month: int, year: int, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Get calendar data for a specific month and year.
    """
    try:
        userID = current_user["id"]
        result = await PaymentController.get_calendar_data(month, year)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e # Re-raise to return the HTTPException response