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
from utils.errors import error_detail
from fastapi import APIRouter, Depends, HTTPException, Query
from controllers.payment_outgoing_controller import PaymentOutgoingController
from controllers.bank_controller import BankController
from controllers.payment_incoming_controller import PaymentIncomingController
from utils.auth_utils import get_current_user
from utils.permission import require
from datetime import datetime, date
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
            raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
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
            raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e # Re-raise to return the HTTPException response

@router.get("/tertunda")
async def pembayaran_tertunda(
    current_user: Annotated[User, Depends(require("payment_outgoing", "read"))],
    bankAccounts: List[int] = Query(None),
):
    """
    Pembayaran yang jatuh temponya sudah lewat tetapi belum disetujui.

    Terpisah dari `GET /calendar` karena jawaban itu sudah DIJUMLAHKAN per
    tanggal — satu baris per hari, tanpa nama dokumen dan tanpa status.
    Daftar yang menuntut tindakan tidak dapat disusun darinya.
    """
    return await CalendarController.tertunda(bankAccounts)


@router.get("/terjadwal")
async def pembayaran_terjadwal(
    current_user: Annotated[User, Depends(require("payment_outgoing", "read"))],
    mulai: date,
    akhir: date | None = None,
    bankAccounts: List[int] = Query(None),
):
    """
    Pembayaran BELUM disetujui sebelum `mulai` (dibawa ke saldo awal), dan
    seluruh pembayaran per tanggal di [mulai, akhir].

    Satu sumber untuk saldo rencana kalender, proyeksi kas, dan unduhan —
    saldo awal dari view `mutation` hanya memuat yang sudah disetujui.
    """
    hasil = await CalendarController.terjadwal(mulai, akhir, bankAccounts)
    if "error" in hasil:
        raise HTTPException(status_code=hasil["status"], detail=error_detail(hasil))
    return hasil


@router.get("/download")
async def download_calendar(
    current_user: Annotated[User, Depends(require("payment_outgoing", "read"))],
    month: int | None = None,
    year: int | None = None,
    start: date | None = None,
    end: date | None = None,
    bankAccounts: List[int] = Query(None),
):
    """
    Data kalender untuk diunduh — satu BULAN, atau satu RENTANG TANGGAL.

    `start` + `end` (keduanya `YYYY-MM-DD`, `end` termasuk) mengalahkan
    `month` + `year`. Rentangnya dibatasi `CalendarController.MAKS_HARI_RENTANG`
    hari, DI SINI — bukan hanya di dialognya. Dialog yang membatasi pilihan
    tidak menghalangi siapa pun memanggil `?start=...&end=...` sendiri, dan
    rentang setahun membuat peramban yang merakit berkasnya diam bermenit-menit
    tanpa pesan apa pun.

    `month` + `year` dipertahankan supaya tab lama yang belum dimuat ulang
    tetap dapat mengunduh.
    """
    try:
        if start is not None or end is not None:
            if start is None or end is None:
                raise HTTPException(
                    status_code=400,
                    detail="Rentang harus menyebut `start` dan `end` sekaligus.",
                )
            result = await CalendarController.download_calendar_rentang(
                start, end, bankAccounts
            )
        else:
            if month is None or year is None:
                raise HTTPException(
                    status_code=400,
                    detail="Sebutkan `month` + `year`, atau `start` + `end`.",
                )
            result = await CalendarController.download_calendar_data(month, year, bankAccounts)
        if "error" in result:
            raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e