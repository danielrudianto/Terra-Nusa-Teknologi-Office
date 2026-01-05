from fastapi import APIRouter, Depends, HTTPException, Request, Query
from controllers.supplier_controller import SupplierController
from schemas.supplier_schema import SupplierCreate, SupplierUpdate
from utils.auth_utils import get_current_user
from typing import Annotated
from utils.auth_utils import User

router = APIRouter()

@router.post("/")
async def create_supplier(
    supplier: SupplierCreate, 
    current_user: Annotated[User, Depends(get_current_user)]
):
    user_id = current_user["id"]
    result = await SupplierController.create_supplier(supplier.model_dump(), user_id)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.get("/{supplier_id}")
async def get_supplier(
    supplier_id: int, 
    current_user: Annotated[User, Depends(get_current_user)]
):
    result = await SupplierController.get_supplier(supplier_id)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.get("/")
async def get_suppliers(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    keyword: str = Query(None),
    page: int = Query(0, ge=0),
    pageSize: int = Query(10, ge=10, le=100)
):
    try:
        result = await SupplierController.get_suppliers(keyword, page, pageSize)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        raise e

@router.put("/")
async def update_supplier(
    supplier: SupplierUpdate, 
    current_user: Annotated[User, Depends(get_current_user)]
):
    user_id = current_user["id"]
    # Note: You'll need to include the ID in the update request body
    result = await SupplierController.update_supplier(supplier.model_dump(), user_id)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.delete("/{supplier_id}")
async def delete_supplier(
    supplier_id: int,
    current_user: Annotated[User, Depends(get_current_user)]
):
    user_id = current_user["id"]
    result = await SupplierController.delete_supplier(supplier_id, user_id)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result