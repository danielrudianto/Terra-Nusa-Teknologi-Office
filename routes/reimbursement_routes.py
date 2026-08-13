from fastapi import APIRouter, Depends, Request, Query
from utils.errors import error_detail
from schemas.reimbursement_schema import ReimbursementCreate, ReimbursementResponse
from controllers.reimbursement_controller import ReimbursementController
from utils.auth_utils import get_current_user
from utils.permission import require
from fastapi import HTTPException
from utils.logger_utils import log_error
from typing import Annotated, Optional
from utils.auth_utils import User

router = APIRouter()

@router.post("/", response_model=ReimbursementResponse)
async def create_reimbursement(
    reimbursement: ReimbursementCreate, 
    current_user: Annotated[User, Depends(require("reimbursement", "create"))]
):
    userID = current_user["id"]
    result = await ReimbursementController.create_reimbursement(reimbursement.model_dump(), userID)
    if "error" in result:
        log_error(f"Error creating reimbursement: {str(result['error'])}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result

@router.put("/approve/{reimbursementID}")
async def approve_reimbursement(
    reimbursementID: int, 
    current_user: Annotated[User, Depends(require("reimbursement", "approve"))]
):
    userID = current_user["id"]
    result = await ReimbursementController.approve_reimbursement(reimbursementID, userID)
    if "error" in result:
        log_error(f"Error approving reimbursement: {str(result['error'])}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result

@router.put("/reject/{reimbursementID}")
async def reject_reimbursement(
    reimbursementID: int, 
    current_user: Annotated[User, Depends(require("reimbursement", "approve"))]
):
    userID = current_user["id"]
    result = await ReimbursementController.reject_reimbursement(reimbursementID, userID)
    if "error" in result:
        log_error(f"Error rejecting reimbursement: {str(result['error'])}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result

@router.get("/")
async def get_reimbursements(
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
    filter: int = Query(0, ge=0),
    sortBy: str = Query("date"),
    sortByDirection: str = Query("desc"),
    keyword: Optional[str] = Query(None),
    isApprove: bool = Query(False),
    isPending: bool = Query(False),
    isDelete: bool = Query(False),
    isPaid: bool = Query(False),
    isUnpaid: bool = Query(False),
    current_user: Annotated[User, Depends(require("reimbursement", "read"))] = None
):
    filterObject = {
        "isApprove": isApprove or filter == 0,
        "isPending": isPending or filter == 0,
        "isDelete": isDelete or filter == 0,
        "isPaid": isPaid or filter == 0,
        "isUnpaid": isUnpaid or filter == 0,
    }

    result = await ReimbursementController.get_reimbursements(
        page, pageSize, filterObject, sortBy, sortByDirection, keyword
    )
    if "error" in result:
        log_error(f"Error getting reimbursements: {str(result['error'])}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result

@router.get("/{reimbursementID}")
async def get_reimbursement(
    reimbursementID: int, 
    current_user: Annotated[User, Depends(require("reimbursement", "read"))]
):
    result = await ReimbursementController.get_reimbursement_by_id(reimbursementID)
    if "error" in result:
        log_error(f"Error getting reimbursement: {str(result['error'])}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result