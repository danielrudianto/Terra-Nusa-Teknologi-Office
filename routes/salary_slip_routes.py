from fastapi import APIRouter, Depends, HTTPException
from utils.logger_utils import log_error, log_info
from utils.auth_utils import get_current_user
from typing import Annotated
from repository.user_repository import UserRepository
from controllers.salary_slip_controller import SalarySlipController
from schemas.salary_slip_schema import SalarySlipCheck
from utils.auth_utils import User

router = APIRouter()

@router.get("/{salary_slip_id}")
async def fetch(salary_slip_id: int, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Fetch salary slip by ID.
    """
    try:
        result = await SalarySlipController.fetchByID(salary_slip_id)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        
        return result
    except HTTPException as e:
        log_error(f"HTTPException during fetch: {str(e.detail)}")
        raise e

@router.get("/")
async def fetch(page: int, pageSize: int, keyword: str, month: int, year: int, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Fetch salary slips with pagination and optional keyword filtering.
    """
    try:
        result = await SalarySlipController.fetch(page, pageSize, keyword, month, year)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        
        return result
    except HTTPException as e:
        log_error(f"HTTPException during fetch: {str(e.detail)}")
        raise e

@router.post("/check")
async def check(salarySlipCheck: SalarySlipCheck, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Check if a salary slip exists for the given user, month, and year.
    """
    try:
        userID = salarySlipCheck.userID
        month = salarySlipCheck.month  
        year = salarySlipCheck.year
        checkResult = await SalarySlipController.check(userID, month, year)
        if "error" in checkResult:
            raise HTTPException(status_code=checkResult["status"], detail=checkResult["error"])
        
        return checkResult
    except HTTPException as e:
        log_error(f"HTTPException during check: {str(e.detail)}")
        raise e

@router.post("/send")
async def send_salary_slip(salarySlipSend: dict, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Send a salary slip.
    """
    try:
        id = salarySlipSend.get('id')
        userID = current_user.id
        sendResult = await SalarySlipController.send(id)
        if "error" in sendResult:
            raise HTTPException(status_code=sendResult["status"], detail=sendResult["error"])
        
        return sendResult
    except HTTPException as e:
        log_error(f"HTTPException during send: {str(e.detail)}")
        raise e

@router.post("/")
async def create_salary_slip(salarySlip: dict, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Create a new salary slip.
    
    Args:
        salarySlip (dict): The salary slip data to be created.
        current_user (User): The currently authenticated user.
    
    Returns:
        dict: The created salary slip data or an error message.
    """
    try:
        userID = current_user.id
        createResult = await SalarySlipController.create(userID, salarySlip)
        if "error" in createResult:
            log_error(f"Error creating salary slip: {createResult['error']}")
            raise HTTPException(status_code=createResult["status"], detail=createResult["error"])
        return createResult
    except HTTPException as e:
        log_error(f"HTTPException during creation: {str(e.detail)}")
        raise e 
    
@router.delete("/{id}")
async def delete_salary_slip(id: int, current_user: Annotated[User, Depends(get_current_user)]):
    try:
        userID = current_user.id
        deleteResult = await SalarySlipController.delete(id, userID)
        if "error" in deleteResult:
            log_error(f"Error deleting salary slip: {deleteResult['error']}")
            raise HTTPException(status_code=deleteResult["status"], detail=deleteResult["error"])
        return deleteResult
    except HTTPException as e:
        log_error(f"HTTPException during deletion: {str(e.detail)}")
        raise e