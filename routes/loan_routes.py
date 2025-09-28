from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from controllers.loan_controller import LoanController
from models.loans_model import Loans
from utils.auth_utils import get_current_user
from models.user_model import User

router = APIRouter()

@router.post("/")
async def create_loan(loan_data:Loans, current_user: Annotated[User, Depends(get_current_user)]):
    try:
        userID = current_user["id"]
        result = await LoanController.create_loan(loan_data.model_dump(), userID)
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e  # Re-raise to return the HTTPException response