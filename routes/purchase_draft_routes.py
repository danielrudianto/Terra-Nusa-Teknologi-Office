from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from utils.auth_utils import get_current_user
from models.user_model import User
from models.purchase_draft_model import PurchaseDraft;
from controllers.purchase_draft_controller import PurchaseDraftController
from utils.logger_utils import log_error

router = APIRouter()

@router.get("/")
async def get_purchae_draft(page: int, pageSize: int, isPending: bool, isApproved: bool, sortBy: str, sortByDirection: str, keyword: str, current_user: Annotated[User, Depends(get_current_user)]):
    result = await PurchaseDraftController.get_purchase_draft(page, pageSize, isPending, isApproved, sortBy, sortByDirection, keyword)
    if "error" in result:
        log_error(f"Error creating purchase: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result

@router.get("/{purchaseDraftID}")
async def get_purchae_draft(purchaseDraftID: int, current_user: Annotated[User, Depends(get_current_user)]):
    result = await PurchaseDraftController.get_purchase_draft_by_id(purchaseDraftID)
    if "error" in result:
        log_error(f"Error creating purchase: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result

@router.post("/")
async def create_purchase_draft(purchase: PurchaseDraft, current_user: Annotated[User, Depends(get_current_user)]):
    userID = current_user["id"]
    result = await PurchaseDraftController.create_purchase_draft(purchase.model_dump(), userID)
    if "error" in result:
        log_error(f"Error creating purchase: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result