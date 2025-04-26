from fastapi import APIRouter, Depends
from models.purchase_model import Purchase
from controllers.purchase_controller import PurchaseController
from utils.error_handler import handle_error
from utils.auth_utils import validate_token
from fastapi import HTTPException

router = APIRouter()

@router.post("/")
async def create_purchase(purchase: Purchase, payload: dict = Depends(validate_token)):
    """
    Create a new purchase. Requires a valid token.
    """
    result = await PurchaseController.create_purchase(purchase.model_dump())
    if "error" in result:
        handle_error(400, result["error"])
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result
