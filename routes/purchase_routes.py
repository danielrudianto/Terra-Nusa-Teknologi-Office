from fastapi import APIRouter, Depends
from models.purchase_model import Purchase
from controllers.purchase_controller import PurchaseController
from utils.auth_utils import validate_token
from fastapi import HTTPException
from utils.logger_utils import log_error

router = APIRouter()

@router.post("/")
async def create_purchase(purchase: Purchase, payload: dict = Depends(validate_token)):
    """
    Create a new purchase. Requires a valid token.
    """
    userID = payload.get("user_id")
    result = await PurchaseController.create_purchase(purchase.model_dump(), userID)
    if "error" in result:
        log_error(f"Error during login: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result
