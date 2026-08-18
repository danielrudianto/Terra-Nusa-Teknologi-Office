from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from controllers.payment_plan_controller import PaymentPlanController
from schemas.payment_plan_schema import PaymentPlanCreate, PaymentPlanUpdate
from utils.errors import error_detail
from utils.permission import require

router = APIRouter()


def _bereskan(result: dict):
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result


@router.get("/")
async def daftar_rencana(
    current_user: Annotated[dict, Depends(require("payment_plan", "read"))],
    awal: date = Query(...),
    akhir: date = Query(...),
    projectName: str = Query(""),
    sertakanBatal: bool = Query(False),
):
    """
    Rencana pengeluaran dalam satu rentang tanggal.

    Rentangnya WAJIB. Tanpa batas, kalender yang membuka bulan mana pun akan
    menarik seluruh riwayat perencanaan — dan itu tumbuh terus tanpa pernah
    menyusut.
    """
    return _bereskan(
        await PaymentPlanController.rentang(
            awal, akhir, projectName, sertakanBatal
        )
    )


@router.get("/ringkasan")
async def ringkasan_rencana(
    current_user: Annotated[dict, Depends(require("payment_plan", "read"))],
    awal: date = Query(...),
    akhir: date = Query(...),
):
    """Jumlah rencana per kategori; dipakai layar posisi kas."""
    return _bereskan(await PaymentPlanController.ringkasan(awal, akhir))


@router.post("/")
async def buat_rencana(
    body: PaymentPlanCreate,
    current_user: Annotated[dict, Depends(require("payment_plan", "create"))],
):
    return _bereskan(
        await PaymentPlanController.buat(body.model_dump(), current_user["id"])
    )


@router.put("/{plan_id}")
async def ubah_rencana(
    plan_id: int,
    body: PaymentPlanUpdate,
    current_user: Annotated[dict, Depends(require("payment_plan", "update"))],
):
    return _bereskan(
        await PaymentPlanController.ubah(
            plan_id, body.model_dump(exclude_unset=True), current_user["id"]
        )
    )


@router.delete("/{plan_id}")
async def hapus_rencana(
    plan_id: int,
    current_user: Annotated[dict, Depends(require("payment_plan", "delete"))],
):
    return _bereskan(
        await PaymentPlanController.hapus(plan_id, current_user["id"])
    )
