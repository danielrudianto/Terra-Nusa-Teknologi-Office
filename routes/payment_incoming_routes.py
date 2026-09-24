from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timedelta, date
from utils.logger_utils import log_error, log_info
from utils.auth_utils import get_current_user
from utils.permission import require
from repository.payment_income_repository import PaymentIncomingRepository
from controllers.payment_incoming_controller import PaymentIncomingController
from utils.auth_utils import User
from utils.errors import error_detail

router = APIRouter()

@router.post("/")
async def create_payment(payment: dict, user: Annotated[User, Depends(require("payment_incoming", "create"))]):
    """
    Create a new payment. Requires a valid token.
    """
    userID = user["id"]
    result = await PaymentIncomingController.create_payment(payment, userID)
    
    if "error" in result:
        log_error(f"Error creating payment: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result

@router.put("/{payment_id}")
async def update_payment(
    payment_id: int,
    payment: dict,
    user: Annotated[User, Depends(require("payment_incoming", "update"))],
):
    """
    Betulkan pembayaran masuk yang salah catat.

    Hanya rekening, tanggal, dan nominal. Faktur asalnya tidak dapat
    dipindah — lihat `PaymentIncomingController.update_payment`.
    """
    result = await PaymentIncomingController.update_payment(
        payment_id, payment, user["id"]
    )
    if "error" in result:
        raise HTTPException(
            status_code=result.get("status", 500), detail=error_detail(result)
        )
    return result


@router.delete("/{payment_id}")
async def delete_payment(
    payment_id: int,
    user: Annotated[User, Depends(require("payment_incoming", "delete"))],
):
    """
    Hapus pembayaran masuk yang tidak pernah terjadi.

    Matriks izin sudah menahannya di level 4; controller memeriksanya lagi,
    supaya rute lain yang kelak memanggilnya tetap terjaga.
    """
    result = await PaymentIncomingController.delete_payment(
        # `user` adalah `Row`, bukan dict — ia TIDAK punya `.get()`.
        # Levelnya diambil seperti di rute pembelian.
        payment_id,
        user["id"],
        user.authenticationLevel or 1,
    )
    if "error" in result:
        raise HTTPException(
            status_code=result.get("status", 500), detail=error_detail(result)
        )
    return result
