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
    # Level diteruskan supaya marjin dan ROE hanya digambar untuk level 5 —
    # gerbangnya di SERVER, bukan di layar. Menyembunyikan blok di peramban
    # tidak menahan siapa pun yang memanggil rutenya langsung.
    result = await FinanceStatusController.get_status(
        int(current_user.get("authenticationLevel") or 0)
    )
    if isinstance(result, dict) and "error" in result:
        # `error_detail`, bukan `result["error"]` mentah: galat berkode
        # dikirim sebagai objek agar layar dapat menerjemahkannya, dan yang
        # belum berkode tetap lewat sebagai teks.
        raise HTTPException(
            status_code=result.get("status", 500), detail=error_detail(result)
        )
    return result


@router.get("/akurasi-rencana")
async def get_akurasi_rencana(
    # Izin yang SAMA dengan ringkasannya: keduanya menceritakan posisi kas
    # perusahaan, dan pintu kedua yang lebih longgar membuat matriks izinnya
    # tidak berlaku lagi.
    current_user: Annotated[dict, Depends(require("finance_status", "read"))],
    mundur: int = 5,
):
    """Rencana kas vs yang benar-benar terjadi, per bulan."""
    result = await FinanceStatusController.akurasi_rencana(mundur)
    if isinstance(result, dict) and "status" in result and "error" in result:
        raise HTTPException(
            status_code=result.get("status", 500), detail=error_detail(result)
        )
    return result


@router.put("/ambang/{kode}")
async def simpan_ambang(
    kode: str,
    payload: dict,
    # `update`, bukan `read`: mengubah pita acuan mengubah cara SELURUH angka
    # di halaman itu dibaca orang. Matriks izin menetapkannya level 5.
    current_user: Annotated[dict, Depends(require("finance_status", "update"))],
):
    """Setel satu pita acuan."""
    result = await FinanceStatusController.simpan_ambang(
        kode, payload, int(current_user.get("id") or 0)
    )
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(
            status_code=result.get("status", 400), detail=error_detail(result)
        )
    return result


@router.delete("/ambang/{kode}")
async def hapus_ambang(
    kode: str,
    current_user: Annotated[dict, Depends(require("finance_status", "update"))],
):
    """Kembalikan satu pita ke bawaannya."""
    result = await FinanceStatusController.hapus_ambang(kode)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(
            status_code=result.get("status", 400), detail=error_detail(result)
        )
    return result
