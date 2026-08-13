from typing import Annotated
from utils.errors import error_detail
from fastapi import APIRouter, Depends, HTTPException
from utils.auth_utils import get_current_user
from utils.permission import require
from schemas.user_schema import UserLogin
from schemas.purchase_schema import (
    PurchaseCreate, PurchaseUpdateStatus, PurchaseCheckRequest,
    PurchaseListResponse
)
from controllers.purchase_controller import PurchaseController
from utils.logger_utils import log_error
from utils.auth_utils import User

router = APIRouter()

@router.post("/", response_model=dict)
async def create_purchase(
    purchase: PurchaseCreate, 
    current_user: Annotated[User, Depends(require("purchase", "create"))]
):
    """
    Create a new purchase.
    """
    userID = current_user.id
    result = await PurchaseController.create_purchase(purchase.model_dump(), userID)
    if "error" in result:
        log_error(f"Error creating purchase: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    return result

@router.post("/check", response_model=dict)
async def check_purchase(
    data: PurchaseCheckRequest, 
    current_user: Annotated[User, Depends(require("purchase", "create"))]
):
    """
    Check if a purchase exists with the given invoice name and purchase order name.
    """
    result = await PurchaseController.check_purchase(data.invoiceName, data.purchaseOrderName)
    if "error" in result:
        log_error(f"Error checking purchase: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result

@router.get("/purchase-order/{purchase_order_name}")
async def get_purchases_by_purchase_order_name(
    purchase_order_name: str,
    current_user: Annotated[User, Depends(require("purchase", "read"))]
):
    """
    Get purchases by purchase order name.
    """
    result = await PurchaseController.get_purchases_by_purchase_order_name(purchase_order_name)
    if "error" in result:
        log_error(f"Error fetching purchases: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    return result

@router.get("/frequent-payment/{supplier_id}", response_model=dict)
async def get_frequent_payment_by_supplier_id(
    supplier_id: int, 
    current_user: Annotated[User, Depends(require("purchase", "read"))]
):
    """
    Get a report of frequent payments by supplier ID.
    """
    result = await PurchaseController.get_frequent_payment_by_supplier_id(supplier_id)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=error_detail(result))
    
    return result

@router.get("/report/project/{projectName}", response_model=dict)
async def get_purchase_report_by_project(
    projectName: str, 
    current_user: Annotated[User, Depends(require("purchase", "read"))]
):
    """
    Get a report of purchases by project name.
    """
    purchases = await PurchaseController.get_purchase_report_by_project(projectName)
    if "error" in purchases:
        raise HTTPException(status_code=purchases["status"], detail=purchases["error"])
    
    return purchases

@router.get("/payments/{purchase_id}")
async def get_payments_by_purchase_id(
    purchase_id: int,
    # Balikannya memuat nama dan nomor rekening pembayar, bukan sekadar
    # nominalnya — sehingga dijaga seperti data pembayaran, bukan pembelian.
    current_user: Annotated[User, Depends(require("payment_outgoing", "read"))],
):
    """
    Get payments by purchase ID.
    """
    purchase = await PurchaseController.get_purchase_by_id(purchase_id)
    if "error" in purchase:
        raise HTTPException(status_code=purchase["status"], detail=purchase["error"])
    
    return purchase

@router.get("/{purchase_id}")
async def get_purchase_by_id(
    purchase_id: int, 
    current_user: Annotated[User, Depends(require("purchase", "read"))]
):
    """
    Get a purchase by ID.
    """
    result = await PurchaseController.get_purchase_by_id(purchase_id)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=error_detail(result))
    return result

@router.get("/", response_model=PurchaseListResponse)
async def get_purchases(
    page: int, 
    pageSize: int, 
    filter: int, 
    sortBy: str, 
    sortByDirection: str, 
    keyword: str | None, 
    current_user: Annotated[User, Depends(require("purchase", "read"))], 
    isDue: bool = False, 
    isNotDue: bool = False, 
    isPaid: bool = False, 
    isUnpaid: bool = False, 
    isDraft: bool = False, 
    isReady: bool = False
):
    """
    Get a list of purchases.
    """
    page = int(page)
    pageSize = int(pageSize)
    filter = int(filter)
    filterObject = {}

    if filter == 0:
        filterObject = {
            "isDue": True,
            "isNotDue": True,
            "isPaid": True,
            "isUnpaid": True,
            "isDraft": True,
            "isReady": True
        }
    else:
        filterObject = {
            "isDue": isDue,
            "isNotDue": isNotDue,
            "isPaid": isPaid,
            "isUnpaid": isUnpaid,
            "isDraft": isDraft,
            "isReady": isReady
        }
    
    try:
        result = await PurchaseController.get_purchases(page, pageSize, filterObject, sortBy, sortByDirection, keyword)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=error_detail(result))
        return result
    except HTTPException as e:
        raise e

@router.put("/update-status", response_model=dict)
async def update_status(
    purchaseStatus: PurchaseUpdateStatus, 
    current_user: Annotated[User, Depends(require("purchase", "update"))]
):
    """
    Update the status of a purchase.
    """
    userID = current_user.id
    result = await PurchaseController.update_status(purchaseStatus.model_dump(), userID)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=error_detail(result))
    
    return result

@router.delete("/{purchase_id}", response_model=dict)
async def delete_purchase(
    purchase_id: int, 
    current_user: Annotated[User, Depends(require("purchase", "delete"))]
):
    """
    Delete a purchase by ID.
    """
    userID = current_user.id
    result = await PurchaseController.delete_purchase(
        purchase_id, userID, current_user.authenticationLevel or 1
    )
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=error_detail(result))
    
    return result