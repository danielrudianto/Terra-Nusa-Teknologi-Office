from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from utils.auth_utils import get_current_user
from utils.permission import require
from repository.user_repository import UserRepository
from models.purchase_draft_model import PurchaseDraft;
from controllers.purchase_draft_controller import PurchaseDraftController
from utils.logger_utils import log_error
from utils.auth_utils import User

router = APIRouter()

@router.get("/")
async def get_purchase_draft(page: int, pageSize: int, isPending: bool, isApproved: bool, sortBy: str, sortByDirection: str, keyword: str, current_user: Annotated[User, Depends(require("purchase_draft", "read"))]):
    result = await PurchaseDraftController.get_purchase_draft(page, pageSize, isPending, isApproved, sortBy, sortByDirection, keyword)
    if "error" in result:
        log_error(f"Error creating purchase: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result

@router.get("/{purchaseDraftID}")
async def get_purchae_draft(purchaseDraftID: int, current_user: Annotated[User, Depends(require("purchase_draft", "read"))]):
    result = await PurchaseDraftController.get_purchase_draft_by_id(purchaseDraftID)
    if "error" in result:
        log_error(f"Error creating purchase: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result

@router.post("/")
async def create_purchase_draft(purchase: PurchaseDraft, current_user: Annotated[User, Depends(require("purchase_draft", "create"))]):
    userID = current_user["id"]
    result = await PurchaseDraftController.create_purchase_draft(purchase.model_dump(), userID)
    if "error" in result:
        log_error(f"Error creating purchase: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result

@router.put("/")
async def update_purchase(purchase: dict, current_user: Annotated[User, Depends(require("purchase_draft", "update"))]):
    """
    Create a new purchase. Requires a valid token.
    """
    userID = current_user["id"]
    result = await PurchaseDraftController.convert_purchase_draft(purchase, userID)
    if "error" in result:
        log_error(f"Error creating purchase: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result

@router.delete("/{purchaseDraftID}")
async def delete_purchase_draft(purchaseDraftID: int, current_user: Annotated[User, Depends(require("purchase_draft", "delete"))]):
    userID = current_user["id"]
    result = await PurchaseDraftController.delete_purchase_draft(purchaseDraftID, userID)
    if "error" in result:
        log_error(f"Error creating purchase: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result