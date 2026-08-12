"""
Rute kalender pembayaran.

Dijaga `payment_outgoing:read`, bukan `calendar:read`.

Isinya jadwal pembayaran keluar, mutasi antarrekening, dan saldo
rekening pada tanggal tersebut — seluruhnya data keuangan. Menjaganya
dengan izin kalender membuat data itu terbaca oleh siapa pun yang
dapat membuka kalender, padahal membuka daftar pembayarannya sendiri
memerlukan akses 3.

Modul `calendar` tetap ada untuk penanda menu; yang menentukan batas
data adalah isinya, bukan halaman yang menampilkannya.
"""

from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, Query
from controllers.payment_outgoing_controller import PaymentOutgoingController
from controllers.bank_controller import BankController
from controllers.payment_incoming_controller import PaymentIncomingController
from utils.auth_utils import get_current_user
from utils.permission import require
from datetime import datetime
from utils.auth_utils import User
from controllers.calendar_controller import CalendarController

router = APIRouter()

@router.get("/")
async def get_calendar_data(month: int, year: int, current_user: Annotated[User, Depends(require("payment_outgoing", "read"))], bankAccounts: List[int] =  Query(None)):
    """
    Get calendar data for a specific month and year.
    """
    try:
        userID = current_user["id"]
        result = await CalendarController.get_calendar_data(month, year, bankAccounts)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e # Re-raise to return the HTTPException response

@router.get("/daily")    
async def get_calendar_data_by_date(date: str, current_user: Annotated[User, Depends(require("payment_outgoing", "read"))], bankAccounts: List[int] = Query(None)):
    """
    Get calendar data for a specific date.
    """
    try:
        userID = current_user["id"]
        dt = datetime.strptime(date, "%Y-%m-%d").date()
        result = await PaymentOutgoingController.get_calendar_data_by_date(dt, bankAccounts)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e # Re-raise to return the HTTPException response

@router.get("/download")
async def download_calendar(month: int, year: int, current_user: Annotated[User, Depends(require("payment_outgoing", "read"))], bankAccounts: List[int] =  Query(None)):
    """
    Download calendar data for a specific month and year.
    """
    try:
        userID = current_user["id"]
        result = await CalendarController.download_calendar_data(month, year, bankAccounts)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e