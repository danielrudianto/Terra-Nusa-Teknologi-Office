from fastapi import APIRouter, HTTPException, Depends
from controllers.tax_controller import TaxController
from utils.logger_utils import log_error
from models.user_model import User
from typing import Annotated
from utils.auth_utils import get_current_user

router = APIRouter()

@router.get("/ppn")
async def fetch_ppn_report(month: int, year: int, current_user: Annotated[User, Depends(get_current_user)]):
    result = await TaxController.get_ppn_report(month, year)
    if "error" in result:
        log_error(f"Error during fetching ppn report: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.get("/pph")
async def fetch_pph_report(month: int, year: int, current_user: Annotated[User, Depends(get_current_user)]):
    result = await TaxController.get_pph_report(month, year)
    if "error" in result:
        log_error(f"Error during fetching ppn report: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.get("/pph-salary")
async def fetch_pph_report(month: int, year: int, current_user: Annotated[User, Depends(get_current_user)]):
    result = await TaxController.get_pph_salary_report(month, year)
    if "error" in result:
        log_error(f"Error during fetching ppn report: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result