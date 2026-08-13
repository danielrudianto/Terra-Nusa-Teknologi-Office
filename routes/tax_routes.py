from fastapi import APIRouter, HTTPException, Depends
from controllers.tax_controller import TaxController
from utils.logger_utils import log_error
from repository.user_repository import UserRepository
from typing import Annotated
from utils.auth_utils import get_current_user
from utils.permission import require
from utils.auth_utils import User

router = APIRouter()

@router.get("/ppn")
async def fetch_ppn_report(month: int, year: int, current_user: Annotated[User, Depends(require("tax", "read"))]):
    result = await TaxController.get_ppn_report(month, year)
    if "error" in result:
        log_error(f"Error during fetching ppn report: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.get("/pph")
async def fetch_pph_report(month: int, year: int, current_user: Annotated[User, Depends(require("tax", "read"))]):
    result = await TaxController.get_pph_report(month, year)
    if "error" in result:
        log_error(f"Error during fetching ppn report: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.get("/pph-salary")
async def fetch_pph_report(month: int, year: int, current_user: Annotated[User, Depends(require("tax", "read"))]):
    result = await TaxController.get_pph_salary_report(month, year)
    if "error" in result:
        log_error(f"Error during fetching ppn report: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.post("/monthly-recap")
async def fetch_monthly_recap(
    params: dict,
    # `read`, bukan `create`: rekap hanya membaca. Dijaga `create`, laporan
    # bulanan tertutup bagi bagian keuangan yang justru menyusunnya.
    current_user: Annotated[User, Depends(require("tax", "read"))],
):
    result = await TaxController.get_monthly_recap(params)
    if "error" in result:
        log_error(f"Error during fetching ppn report: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result