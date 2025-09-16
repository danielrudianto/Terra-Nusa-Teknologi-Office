from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timedelta, date
from utils.logger_utils import log_error, log_info
from utils.auth_utils import get_current_user
from models.payment_incoming_model import PaymentIncoming
from controllers.payment_incoming_controller import PaymentIncomingController

router = APIRouter()

@router.post("/")
async def create_payment(payment: PaymentIncoming, user: Annotated[dict, Depends(get_current_user)]):
    """
    Create a new payment. Requires a valid token.
    """
    userID = user["id"]
    result = await PaymentIncomingController.create_payment(payment.model_dump(), userID)
    
    if "error" in result:
        log_error(f"Error creating payment: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result