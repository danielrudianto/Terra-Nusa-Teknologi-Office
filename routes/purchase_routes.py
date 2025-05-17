from fastapi import APIRouter, Depends
from models.purchase_model import Purchase
from controllers.purchase_controller import PurchaseController
from utils.auth_utils import get_current_user
from fastapi import HTTPException
from utils.logger_utils import log_error
from typing import Annotated
from utils.auth_utils import User

router = APIRouter()

@router.post("/")
async def create_purchase(purchase: Purchase, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Create a new purchase. Requires a valid token.
    """
    userID = current_user["id"]
    result = await PurchaseController.create_purchase(purchase.model_dump(), userID)
    if "error" in result:
        log_error(f"Error during login: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result

@router.get("/")
async def get_purchases(page: int):
    """
    Get a list of purchases. Requires a valid token.
    """
    page = int(page)
    try:
        result = await PurchaseController.get_purchases(page)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e