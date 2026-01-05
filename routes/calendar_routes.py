from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, Query
from controllers.payment_outgoing_controller import PaymentOutgoingController
from controllers.bank_controller import BankController
from controllers.payment_incoming_controller import PaymentIncomingController
from utils.auth_utils import get_current_user
from datetime import datetime
from utils.auth_utils import User
from controllers.calendar_controller import CalendarController

router = APIRouter()

@router.get("/")
async def get_calendar_data(month: int, year: int, current_user: Annotated[User, Depends(get_current_user)], bankAccounts: List[int] =  Query(None)):
    """
    Get calendar data for a specific month and year.
    """
    try:
        userID = current_user["id"]
        result = await CalendarController.get_calendar_data(month, year, bankAccounts)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e # Re-raise to return the HTTPException response

@router.get("/daily")    
async def get_calendar_data_by_date(date: str, current_user: Annotated[User, Depends(get_current_user)], bankAccounts: List[int] = Query(None)):
    """
    Get calendar data for a specific date.
    """
    try:
        userID = current_user["id"]
        dt = datetime.strptime(date, "%Y-%m-%d").date()
        result = await PaymentOutgoingController.get_calendar_data_by_date(dt, bankAccounts)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e # Re-raise to return the HTTPException response