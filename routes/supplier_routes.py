from fastapi import APIRouter, Depends, HTTPException, Request
from controllers.supplier_controller import SupplierController
from models.supplier_model import Supplier
from utils.auth_utils import get_current_user
from typing import Annotated
from utils.auth_utils import User

router = APIRouter()

@router.post("/")
async def create_supplier(supplier: Supplier, current_user: Annotated[User, Depends(get_current_user)]):
    userID = current_user["id"]
    result = await SupplierController.create_supplier(supplier.model_dump(), userID)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.get("/{supplier_id}")
async def get_supplier(supplier_id: int, current_user: Annotated[User, Depends(get_current_user)]):
    result = await SupplierController.get_supplier(supplier_id)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result
    
@router.get("/")
async def get_suppliers(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
    keyword = request.query_params.get("keyword")
    page = int(request.query_params.get("page", 1))
    pageSize = int(request.query_params.get("pageSize", 10))

    try:
        result = await SupplierController.get_suppliers(keyword, page, pageSize)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e
    
@router.put("/")
async def update_supplier(supplier: Supplier, current_user: Annotated[User, Depends(get_current_user)]):
    userID = current_user["id"]
    result = await SupplierController.update_supplier(supplier.model_dump(), userID)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result