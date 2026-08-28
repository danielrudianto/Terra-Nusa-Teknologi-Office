from fastapi import APIRouter, HTTPException, Depends
from utils.errors import error_detail
from controllers.tax_controller import TaxController
from repository.audit_log_repository import AuditLogRepository
from utils.logger_utils import log_error
from repository.user_repository import UserRepository
from typing import Annotated
from utils.auth_utils import get_current_user
from utils.permission import require
from utils.auth_utils import User

router = APIRouter()

@router.get("/ppn")
async def fetch_ppn_report(month: int, year: int, current_user: Annotated[User, Depends(require("tax", "read"))]):
    await AuditLogRepository.catat_akses_laporan("ppn", f"Laporan PPN {month}/{year}")
    result = await TaxController.get_ppn_report(month, year)
    if "error" in result:
        log_error(f"Error during fetching ppn report: {str(result['error'])}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result

@router.get("/ppn-position")
async def fetch_ppn_position(month: int, year: int, current_user: Annotated[User, Depends(require("tax", "read"))]):
    await AuditLogRepository.catat_akses_laporan("ppn_posisi", f"Posisi PPN {month}/{year}")
    result = await TaxController.get_ppn_position(month, year)
    if isinstance(result, dict) and "error" in result:
        log_error(f"Error during fetching ppn position: {str(result['error'])}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result

@router.get("/pph")
async def fetch_pph_report(month: int, year: int, current_user: Annotated[User, Depends(require("tax", "read"))]):
    await AuditLogRepository.catat_akses_laporan("pph", f"Laporan PPh {month}/{year}")
    result = await TaxController.get_pph_report(month, year)
    if "error" in result:
        log_error(f"Error during fetching ppn report: {str(result['error'])}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result

@router.get("/pph-salary")
async def fetch_pph_report(month: int, year: int, current_user: Annotated[User, Depends(require("tax", "read"))]):
    await AuditLogRepository.catat_akses_laporan("pph_gaji", f"Laporan PPh gaji {month}/{year}")
    result = await TaxController.get_pph_salary_report(month, year)
    if "error" in result:
        log_error(f"Error during fetching ppn report: {str(result['error'])}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result

@router.post("/monthly-recap")
async def fetch_monthly_recap(
    params: dict,
    # `read`, bukan `create`: rekap hanya membaca. Dijaga `create`, laporan
    # bulanan tertutup bagi bagian keuangan yang justru menyusunnya.
    current_user: Annotated[User, Depends(require("tax", "read"))],
):
    await AuditLogRepository.catat_akses_laporan("rekap_bulanan", "Rekap pajak bulanan")
    result = await TaxController.get_monthly_recap(params)
    if "error" in result:
        log_error(f"Error during fetching ppn report: {str(result['error'])}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result