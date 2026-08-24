from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timedelta, date
from utils.logger_utils import log_error, log_info
from utils.auth_utils import get_current_user
from utils.permission import require
from repository.payment_income_repository import PaymentIncomingRepository
from controllers.payment_incoming_controller import PaymentIncomingController
from utils.auth_utils import User

router = APIRouter()

@router.post("/")
async def create_payment(payment: dict, user: Annotated[User, Depends(require("payment_incoming", "create"))]):
    """
    Create a new payment. Requires a valid token.
    """
    userID = user["id"]
    result = await PaymentIncomingController.create_payment(payment, userID)
    
    if "error" in result:
        log_error(f"Error creating payment: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result