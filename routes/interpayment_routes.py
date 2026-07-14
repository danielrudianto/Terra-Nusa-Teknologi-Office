from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from controllers.interpayment_controller import InterpaymentController
from schemas.interpayment_schema import InterpaymentCreate, CreateInterpaymentResponse, InterpaymentListResponse
from utils.auth_utils import get_current_user, User
from utils.logger_utils import log_error

router = APIRouter()

@router.post("/", response_model=CreateInterpaymentResponse)
async def create_interpayment(interpayment: InterpaymentCreate, user: Annotated[User, Depends(get_current_user)]):
    """
    Create a new interpayment. Requires a valid token.
    """
    userID = user["id"]
    interpayment_data = interpayment.dict()
    interpayment_data["createdBy"] = userID
    result = await InterpaymentController.create_interpayment(interpayment_data)
    if "error" in result:
        log_error(f"Error creating interpayment: {result['error']}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result

@router.delete("/{interpaymentID}")
async def delete_interpayment(interpaymentID: int, user: Annotated[User, Depends(get_current_user)]):
    userID = user["id"]
    result = await InterpaymentController.delete_interpayment(interpaymentID, userID)
    if "error" in result:
        log_error(f"Error deleting interpayment: {result['error']}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result

@router.get("/", response_model=InterpaymentListResponse)
async def get_interpayments(
    page: int,
    pageSize: int,
    start: str,
    end: str,
    user: Annotated[User, Depends(get_current_user)],
    sortBy: str = "date",
    sortByDirection: str = "desc",
):
    """
    Get a list of interpayments with pagination, filtering, and sorting.
    """
    filterObject = {}
    result = await InterpaymentController.get_interpayments(
        page, pageSize, start, end, filterObject, sortBy, sortByDirection
    )
    
    if "error" in result:
        log_error(f"Error fetching interpayments: {result['error']}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result

@router.get("/{interpaymentID}")
async def get_interpayment_detail(
    interpaymentID: int,
    user: Annotated[User, Depends(get_current_user)],
):
    """
    Get the full detail of a single interpayment, including both bank accounts
    and the audit trail (createdBy / createdAt / deletedBy / deletedAt).
    """
    result = await InterpaymentController.get_interpayment_detail(interpaymentID)
 
    if "error" in result:
        log_error(f"Error fetching interpayment detail: {result['error']}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
 
    return result


@router.get("/calendar")
async def get_interpayment_calendar_data(
    month: int,
    year: int,
    bankAccountID: list[int],
    user: Annotated[User, Depends(get_current_user)]
):
    """
    Get interpayment data for calendar view.
    """
    result = await InterpaymentController.get_interpayment_calendar_data(month, year, bankAccountID)
    
    if "error" in result:
        log_error(f"Error fetching interpayment calendar data: {result['error']}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result

@router.get("/calendar/date")
async def get_interpayment_calendar_data_by_date(
    date: int,
    month: int,
    year: int,
    user: Annotated[User, Depends(get_current_user)],
    bankAccountID: list[int] | None = None,
):
    """
    Get interpayment data for specific date in calendar view.
    """
    result = await InterpaymentController.get_interpayment_calendar_data_by_date(date, month, year, bankAccountID)
    
    if "error" in result:
        log_error(f"Error fetching interpayment calendar data by date: {result['error']}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result