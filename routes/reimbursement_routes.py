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

@router.post("/upload")
async def upload_reimbursement(request: Request, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Upload a reimbursement. Requires a valid token.
    """
    form = await request.form()
    # Get the file
    attachment = form.get("file")
    # Get the reimbursement data
    reimbursementID  = form.get("reimbursementID")
    # Upload the file
    file = open("reimbursements/" + reimbursementID + ".pdf", "wb")
    file.write(attachment.file.read())
    file.close()

@router.get("/")
async def get_reimbursements(page: int):
    """
    Get all reimbursements. Requires a valid token.
    """
    result = await ReimbursementController.get_reimbursements(page)
    if "error" in result:
        log_error(f"Error during getting reimbursements: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result
