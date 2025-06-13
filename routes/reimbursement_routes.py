from fastapi import APIRouter, Depends, Request
from models.reimbursement_model import Reimbursement
from controllers.reimbursement_controller import ReimbursementController
from utils.auth_utils import get_current_user
from fastapi import HTTPException
from utils.logger_utils import log_error
from typing import Annotated
from utils.auth_utils import User

router = APIRouter()

@router.post("/")
async def create_reimbursement(reimbursement: Reimbursement, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Create a new purchase. Requires a valid token.
    """
    userID = current_user["id"]
    result = await ReimbursementController.create_reimbursement(reimbursement.model_dump(), userID)
    if "error" in result:
        log_error(f"Error during creating reimbursement: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.put("/approve/{reimbursementID}")
async def approve_reimbursement(reimbursementID: int, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Approve a reimbursement. Requires a valid token.
    """
    userID = current_user["id"]
    result = await ReimbursementController.approve_reimbursement(reimbursementID, userID)
    if "error" in result:
        log_error(f"Error during approving reimbursement: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.put("/reject/{reimbursementID}")
async def reject_reimbursement(reimbursementID: int, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Reject a reimbursement. Requires a valid token.
    """
    userID = current_user["id"]
    result = await ReimbursementController.reject_reimbursement(reimbursementID, userID)
    if "error" in result:
        log_error(f"Error during rejecting reimbursement: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.post("/upload")
async def upload_reimbursement(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Upload a reimbursement. Requires a valid token.
    """
    # form = await request.form()
    # # Get the file
    # attachment = form.get("file")
    # # Get the reimbursement data
    # reimbursementID  = form.get("reimbursementID")
    # # Upload the file
    # file = open("reimbursements/" + reimbursementID + ".pdf", "wb")
    # file.write(attachment.file.read())
    # file.close()

@router.get("/")
async def get_reimbursements(
    page: int, 
    pageSize: int, 
    filter: int, 
    sortBy: str, 
    sortByDirection: str, 
    keyword: str | None, 
    current_user: Annotated[User, Depends(get_current_user)], 
    isApprove: bool = False, 
    isPending: bool = False, 
    isDelete: bool = False, 
    isPaid: bool = False, 
    isUnpaid: bool = False
):
    """
    Get all reimbursements. Requires a valid token.
    """
    page = int(page)
    pageSize = int(pageSize)
    filter = int(filter)
    filterObject = {}

    if(filter == 0):
        filterObject = {
            "isApprove": True,
            "isPending": True,
            "isDelete": True,
            "isPaid": True,
            "isUnpaid": True,
        }
    else :
        filterObject = {
            "isApprove": isApprove,
            "isPending": isPending,
            "isDelete": isDelete,
            "isPaid": isPaid,
            "isUnpaid": isUnpaid,
        }

    result = await ReimbursementController.get_reimbursements(page, pageSize, filterObject, sortBy, sortByDirection, keyword)
    if "error" in result:
        log_error(f"Error during getting reimbursements: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.get("/{reimbursementID}")
async def get_reimbursement(reimbursementID: str, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Get a reimbursement by ID. Requires a valid token.
    """
    result = await ReimbursementController.get_reimbursement_by_id(reimbursementID)
    if "error" in result:
        log_error(f"Error during getting reimbursement: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result