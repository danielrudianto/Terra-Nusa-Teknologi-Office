from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from controllers.bank_controller import BankController
from utils.auth_utils import get_current_user
from models.user_model import User
from models.interpayment_model import Interpayment
from controllers.interpayment_controller import InterpaymentController
from utils.logger_utils import log_error

router = APIRouter()

@router.post("/")
async def create_interpayment(interpayment: Interpayment, user: Annotated[User, Depends(get_current_user)]):
    """
    Create a new interpayment. Requires a valid token.
    """
    userID = user["id"]
    interpayment_data = interpayment.model_dump()
    interpayment_data["createdBy"] = userID
    result = await InterpaymentController.create_interpayment(interpayment_data)
    if "error" in result:
        log_error(f"Error creating interpayment: {result['error']}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result

@router.get("/")
async def get_interpayments(
    page: int,
    pageSize: int,
    user: Annotated[User, Depends(get_current_user)],
    sortBy: str = "date",
    sortByDirection: str = "desc",
):
    """
    Get a list of interpayments with pagination, filtering, and sorting.
    """
    filterObject = {}
    result = await InterpaymentController.get_interpayments(
        page, pageSize, filterObject, sortBy, sortByDirection
    )
    
    if "error" in result:
        log_error(f"Error fetching interpayments: {result['error']}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result