from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from controllers.finance_status_controller import FinanceStatusController
from utils.errors import error_detail
from utils.permission import require

router = APIRouter()


@router.get("/")
async def get_finance_status(
    # Modul `finance_status` menetapkan baca level 4; tidak ada tindakan
    # lain karena rute ini tidak pernah menulis apa pun.
    current_user: Annotated[dict, Depends(require("finance_status", "read"))],
):
    """Posisi keuangan: kas, piutang, utang usaha, pinjaman, quick ratio."""
    result = await FinanceStatusController.get_status()
    if isinstance(result, dict) and "error" in result:
        # `error_detail`, bukan `result["error"]` mentah: galat berkode
        # dikirim sebagai objek agar layar dapat menerjemahkannya, dan yang
        # belum berkode tetap lewat sebagai teks.
        raise HTTPException(
            status_code=result.get("status", 500), detail=error_detail(result)
        )
    return result
