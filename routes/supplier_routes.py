from fastapi import APIRouter, Depends, HTTPException
from controllers.supplier_controller import SupplierController
from models.supplier_model import Supplier
from utils.auth_utils import validate_token

router = APIRouter()

@router.post("/")
async def create_supplier(supplier: Supplier, payload: dict = Depends(validate_token)):
    try:
        userID = payload.get("user_id")
        result = await SupplierController.create_supplier(supplier.model_dump(), userID)
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e  # Re-raise to return the HTTPException response