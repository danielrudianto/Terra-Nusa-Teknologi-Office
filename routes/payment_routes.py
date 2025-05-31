from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timedelta
from utils.logger_utils import log_error, log_info
import json
from utils.auth_utils import get_current_user
from models.payment_model import Payment
from controllers.payment_controller import PaymentController

router = APIRouter()

@router.post("/")
async def create_payment(payment: Payment, user: Annotated[dict, Depends(get_current_user)]):
    """
    Create a new payment. Requires a valid token.
    """
    userID = user["id"]
    result = await PaymentController.create_payment(payment.model_dump(), userID)
    
    if "error" in result:
        log_error(f"Error creating payment: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result
