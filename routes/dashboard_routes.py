from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query

from utils.auth_utils import get_current_user, User
from utils.permission import require
from controllers.dashboard_controller import DashboardController

router = APIRouter()


@router.get("/cash-position")
async def get_cash_position(
    current_user: Annotated[User, Depends(require("dashboard", "read"))],
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