from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from controllers.loan_controller import LoanController
from schemas.loan_schema import LoanCreate, CreateLoanResponse, LoanListResponse, LoanPaymentsResponse
from utils.auth_utils import get_current_user, User

router = APIRouter()

@router.post("/", response_model=CreateLoanResponse)
async def create_loan(loan_data: LoanCreate, current_user: Annotated[User, Depends(get_current_user)]):
    """Create a new loan."""
    try:
        user_id = current_user["id"]
        result = await LoanController.create_loan(loan_data.dict(), user_id)
        return result
    except HTTPException as e:
        raise e

@router.get("/payments/{loan_id}", response_model=LoanPaymentsResponse)
async def get_loan_payments(loan_id: int, current_user: Annotated[User, Depends(get_current_user)]):
    """Get loan details with its payments."""
    try:
        user_id = current_user["id"]
        loan = await LoanController.get_loan_by_id(loan_id)
        payments = await LoanController.get_payments_by_loan_id(loan_id)
        
        return {
            "loan": dict(loan) if loan else {},
            "payments": payments
        }
    except HTTPException as e:
        raise e

@router.get("/", response_model=LoanListResponse)
async def get_loans(
    page: int, 
    pageSize: int, 
    isPaid: bool, 
    isUnpaid: bool, 
    sortBy: str, 
    current_user: Annotated[User, Depends(get_current_user)],
    sortByDirection: str, 
    keyword: str | None = None, 
):
    """Get paginated list of loans with filtering and sorting."""
    try:
        user_id = current_user["id"]
        result = await LoanController.get_loans(page, pageSize, isPaid, isUnpaid, sortBy, sortByDirection, keyword)
        return result
    except HTTPException as e:
        raise e