from typing import Annotated, Optional
from utils.errors import error_detail
from fastapi import APIRouter, Depends, HTTPException, Query
from controllers.purchase_order_controller import PurchaseOrderController
from schemas.purchase_order_schema import (
    PurchaseOrderCreate, 
    CreatePurchaseOrderResponse, 
    PurchaseOrderResponse,
    PurchaseOrderListResponse,
    PurchaseOrderStatus
)
from utils.auth_utils import get_current_user, User
from utils.permission import require

router = APIRouter()

@router.post("/", response_model=CreatePurchaseOrderResponse)
async def create_purchase_order(
    purchase_order_data: PurchaseOrderCreate,
    current_user: Annotated[User, Depends(require("purchase_order", "create"))]
):
    """
    Create a new purchase order with auto-generated name.
    The name will be generated based on the project name (e.g., 001, 002, 003).
    """
    try:
        user_id = current_user["id"]
        result = await PurchaseOrderController.create_purchase_order(
            purchase_order_data.dict(), 
            user_id
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=result.get("status", 500), 
                detail=error_detail(result)
            )
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/{purchase_order_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order_by_id(
    purchase_order_id: int,
    current_user: Annotated[User, Depends(require("purchase_order", "read"))]
):
    """
    Get a purchase order by its ID.
    """
    try:
        result = await PurchaseOrderController.get_purchase_order_by_id(purchase_order_id)
        
        if "error" in result:
            raise HTTPException(
                status_code=result.get("status", 500), 
                detail=error_detail(result)
            )
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=PurchaseOrderListResponse)
async def get_all_purchase_orders(
    current_user: Annotated[User, Depends(require("purchase_order", "read"))],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    keyword: str = Query(None, description="Search by PO number, project, or supplier"),
    sortBy: str = Query(None, description="Sort column: date, value, supplier, project, name, status"),
    sortByDirection: str = Query("desc", description="Sort direction: asc or desc"),
):
    """
    Get all purchase orders with pagination.
    """
    try:
        result = await PurchaseOrderController.get_all_purchase_orders(
            page, page_size, keyword, sortBy, sortByDirection
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=result.get("status", 500), 
                detail=error_detail(result)
            )
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{purchase_order_id}/status")
async def update_purchase_order_status(
    purchase_order_id: int,
    status: PurchaseOrderStatus,
    current_user: Annotated[User, Depends(require("purchase_order", "approve"))]
):
    """
    Update the status of a purchase order.
    """
    try:
        user_id = current_user["id"]
        result = await PurchaseOrderController.update_purchase_order_status(
            purchase_order_id, 
            status.value, 
            user_id
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=result.get("status", 500), 
                detail=error_detail(result)
            )
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{purchase_order_id}")
async def delete_purchase_order(
    purchase_order_id: int,
    current_user: Annotated[User, Depends(require("purchase_order", "delete"))]
):
    """
    Soft delete a purchase order.
    """
    try:
        user_id = current_user["id"]
        result = await PurchaseOrderController.delete_purchase_order(purchase_order_id, user_id)
        
        if "error" in result:
            raise HTTPException(
                status_code=result.get("status", 500), 
                detail=error_detail(result)
            )
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))