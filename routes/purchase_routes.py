from fastapi import APIRouter, Depends
from models.purchase_model import Purchase, PurchaseStatus, PurchaseUpdateStatus
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
        log_error(f"Error creating purchase: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result

@router.get("/report/project")
async def get_purchase_report_by_project(projectName: str, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Get a report of purchases by project name. Requires a valid token.
    """
    result = await PurchaseController.get_purchase_report_by_project(projectName)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result

@router.get("/payments/{purchase_id}")
async def get_payments_by_purchase_id(purchase_id: int, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Get payments by purchase ID. Requires a valid token.
    """
    purchase = await PurchaseController.get_purchase_by_id(purchase_id)
    result = await PurchaseController.get_payments_by_purchase_id(purchase_id)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return {
        "purchase": purchase,
        "payments": result
    }

@router.get("/{purchase_id}")
async def get_purchase_by_id(purchase_id: int, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Get a purchase by ID. Requires a valid token.
    """
    result = await PurchaseController.get_purchase_by_id(purchase_id)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.get("/")
async def get_purchases(page: int, pageSize: int, filter: int, sortBy: str, sortByDirection: str, keyword: str | None, current_user: Annotated[User, Depends(get_current_user)], isDue: bool = False, isNotDue: bool = False, isPaid: bool = False, isUnpaid: bool = False, isDraft: bool = False, isReady: bool = False):
    """
    Get a list of purchases. Requires a valid token.
    """
    page = int(page)
    pageSize = int(pageSize)
    filter = int(filter)
    filterObject = {}

    if(filter == 0):
        filterObject = {
            "isDue": True,
            "isNotDue": True,
            "isPaid": True,
            "isUnpaid": True,
            "isDraft": True,
            "isReady": True
        }
    else :
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
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        raise e
    
@router.put("/update-status")
async def update_status(purchaseStatus: PurchaseUpdateStatus, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Update the status of a purchase. Requires a valid token.
    """
    userID = current_user["id"]
    result = await PurchaseController.update_status(purchaseStatus.model_dump(), userID)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result