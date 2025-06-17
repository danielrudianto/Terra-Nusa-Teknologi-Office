from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timedelta
from utils.logger_utils import log_error, log_info
import json
from utils.auth_utils import get_current_user
from models.payment_outgoing_model import PaymentOutgoing
from controllers.payment_controller import PaymentController

router = APIRouter()

@router.post("/")
async def create_payment(payment: PaymentOutgoing, user: Annotated[dict, Depends(get_current_user)]):
    """
    Create a new payment. Requires a valid token.
    """
    userID = user["id"]
    result = await PaymentController.create_payment(payment.model_dump(), userID)
    
    if "error" in result:
        log_error(f"Error creating payment: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result

@router.get("/{paymentID}")
async def get_payment_by_id(paymentID: int, user: Annotated[dict, Depends(get_current_user)]):
    """
    Get a payment by its ID. Requires a valid token.
    """
    result = await PaymentController.get_payment_by_id(paymentID)
    
    if "error" in result:
        log_error(f"Error fetching payment with ID {paymentID}: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result

@router.get("/")
async def get_payments(
    page: int,
    pageSize: int,
    user: Annotated[dict, Depends(get_current_user)],
    sortBy: str = "createdAt",
    sortByDirection: str = "desc",
    isPending: bool = False, 
    isApproved: bool = False, 
    isRejected: bool = False, 
):
    """
    Get a list of payments with pagination, filtering, and sorting.
    """
    filterObject = {
        "isApproved": isApproved,
        "isPending": isPending,
        "isRejected": isRejected,
    }
    result = await PaymentController.get_payments(
        page, pageSize, filterObject, sortBy, sortByDirection
    )
    
    if "error" in result:
        log_error(f"Error fetching payments: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result

@router.put("/approve/{paymentID}")
async def update_payment_status(
    paymentID: int,
    user: Annotated[dict, Depends(get_current_user)]
):
    """
    Approve a payment by its ID. Requires a valid token.
    """
    userID = user["id"]
    result = await PaymentController.update_payment_status(paymentID, "approve", userID)
    print(result)
    
    if "error" in result:
        log_error(f"Error approving payment with ID {paymentID}: {result['error']}")
        raise HTTPException(status_code=result['status'], detail=result['error'])
    
    return result

@router.put("/reject/{paymentID}")
async def reject_payment_status(
    paymentID: int,
    user: Annotated[dict, Depends(get_current_user)]
):
    """
    Reject a payment by its ID. Requires a valid token.
    """
    userID = user["id"]
    result = await PaymentController.update_payment_status(paymentID, "reject", userID)
    
    if "error" in result:
        log_error(f"Error rejecting payment with ID {paymentID}: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result