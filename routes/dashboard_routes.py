from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query

from utils.auth_utils import get_current_user, User
from utils.permission import require
from controllers.dashboard_controller import DashboardController

router = APIRouter()


@router.get("/cash-position")
async def get_cash_position(
    # Dijaga `bank:read`, bukan `dashboard:read`.
    #
    # Yang dikembalikan adalah nama bank, nama dan nomor rekening, beserta
    # saldonya. Menjaganya dengan izin dasbor membuat data itu terbaca oleh
    # siapa pun yang dapat membuka beranda — termasuk staf procurement —
    # padahal membuka daftar rekeningnya sendiri memerlukan akses 3.
    #
    # Batas sebuah data ditentukan oleh isinya, bukan oleh halaman yang
    # kebetulan menampilkannya.
    current_user: Annotated[User, Depends(require("bank", "read"))],
    bankAccounts: List[int] = Query(None),
):
    """Current cash position across bank accounts.

    Balances come from the latest row of the `mutation` view per account, so
    they reflect the real running balance (not an assumed zero start).

    Optional `?bankAccounts=1,2,3` filters to specific accounts; omit for all.
    """
    try:
        result = await DashboardController.cash_position(bankAccounts)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException:
        raise