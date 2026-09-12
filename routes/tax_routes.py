from fastapi import APIRouter, HTTPException, Depends
from utils.errors import error_detail, ErrorCode
from controllers.tax_controller import TaxController
from repository.audit_log_repository import AuditLogRepository
from utils.logger_utils import log_error
from repository.user_repository import UserRepository
from typing import Annotated
from utils.auth_utils import get_current_user
from utils.permission import require, is_allowed
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

@router.get("/pph-position")
async def fetch_pph_position(month: int, year: int, current_user: Annotated[User, Depends(require("tax", "read"))]):
    await AuditLogRepository.catat_akses_laporan("pph_posisi", f"Posisi PPh {month}/{year}")
    result = await TaxController.get_pph_position(month, year)
    if isinstance(result, dict) and "error" in result:
        log_error(f"Error during fetching pph position: {str(result['error'])}")
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
    """
    Rekap PPh 21 per karyawan.

    Menuntut izin GAJI, bukan hanya izin pajak.

    Yang dikirimnya bukan ringkasan pajak melainkan **daftar gaji seluruh
    karyawan**: gaji pokok, tunjangan transport, uang makan, lembur, tiap
    baris tunjangan dan potongan, beserta PPh-nya. `salary_slip` termasuk
    `MODUL_WILAYAH_MUTLAK` justru supaya angka itu tidak terbuka menurut
    tangga level — sementara `tax` tidak, dan matriksnya membukanya sejak
    level 3.

    Akibatnya seorang general manager (level 4, dan menurut rancangannya
    tidak bermendepartemen) ditolak di `GET /salary-slips` lalu memperoleh
    seluruh angka yang sama dari alamat ini. Daftar aktivitas sudah lebih
    dulu ditutup bagi level 4 persis supaya tidak menjadi pintu belakang ke
    data ini; alamat ini adalah pintu depannya.

    Kedua divisi yang memang memakai layar ini — FAT dan konsultan — sudah
    memegang `salary_slip` di `department_modules`, sehingga penjagaan ini
    tidak menutup siapa pun yang selama ini berhak.
    """
    if not await is_allowed(current_user, "salary_slip", "read"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": ErrorCode.FORBIDDEN,
                "message": (
                    "Laporan ini memuat rincian gaji; diperlukan izin slip gaji."
                ),
            },
        )
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