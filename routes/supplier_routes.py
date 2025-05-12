from fastapi import APIRouter, Depends, HTTPException, Request
from controllers.supplier_controller import SupplierController
from models.supplier_model import Supplier
from utils.auth_utils import validate_token

router = APIRouter()

@router.post("/")
async def create_supplier(supplier: Supplier, payload: dict = Depends(validate_token)):
    try:
        userID = payload.get("user_id")
        print(userID)
        result = await SupplierController.create_supplier(supplier.model_dump(), userID)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e  # Re-raise to return the HTTPException response
    
@router.get("/")
async def get_suppliers(request: Request, payload: dict = Depends(validate_token)):
    keyword = request.query_params.get("keyword")
    page = int(request.query_params.get("page", 1))
    try:
        result = await SupplierController.get_suppliers(keyword, page)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e