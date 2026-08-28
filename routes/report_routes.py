from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from repository.laba_rugi_repository import LabaRugiRepository
from utils.auth_utils import User
from utils.errors import error_detail
from utils.permission import require

router = APIRouter()


@router.get("/laba-rugi")
async def laba_rugi(
    # Sama seperti posisi keuangan: laporan seluruh keuangan perusahaan hanya
    # untuk FAT (modul `finance_status`, baca level 4). Membukanya lebih luas
    # menjadikan halaman ini pintu belakang ke angka yang sudah ditutup.
    current_user: Annotated[User, Depends(require("finance_status", "read"))],
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
):
    """
    Laba rugi konsolidasi (akrual) — bulan berjalan + akumulasi tahun berjalan.

    "Versi kita" untuk dicocokkan dengan pembukuan akuntan; tiap baris dapat
    ditelusuri ke kategori dokumennya. Lihat `repository/laba_rugi_repository`.
    """
    hasil = await LabaRugiRepository.laba_rugi(month, year)
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(
            status_code=hasil.get("status", 500), detail=error_detail(hasil)
        )
    return hasil
