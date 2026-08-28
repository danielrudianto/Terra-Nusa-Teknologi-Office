from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from repository.laba_rugi_repository import LabaRugiRepository
from repository.audit_log_repository import AuditLogRepository
from utils.auth_utils import get_current_user, User
from utils.errors import error_detail

router = APIRouter()


@router.get("/laba-rugi")
async def laba_rugi(
    current_user: Annotated[User, Depends(get_current_user)],
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
):
    """
    Laba rugi konsolidasi (akrual) — bulan berjalan + akumulasi tahun berjalan.

    HANYA pemilik usaha (level 5). Digate langsung ke LEVEL, bukan ke modul
    divisi: laba rugi menyeluruh adalah angka pemilik, dan owner belum tentu
    berada di divisi FAT — memakai izin `finance_status` justru bisa menutup
    aksesnya sendiri. Batasnya ditegakkan di server, bukan sekadar disembunyikan
    di sidenav.

    "Versi kita" untuk dicocokkan dengan pembukuan akuntan; tiap baris dapat
    ditelusuri ke kategori dokumennya. Lihat `repository/laba_rugi_repository`.
    """
    if int(current_user["authenticationLevel"] or 1) < 5:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FORBIDDEN",
                "message": "Laporan laba rugi hanya untuk pemilik usaha (level 5).",
            },
        )

    await AuditLogRepository.catat_akses_laporan(
        "laba_rugi", f"Laba rugi {month}/{year}"
    )

    hasil = await LabaRugiRepository.laba_rugi(month, year)
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(
            status_code=hasil.get("status", 500), detail=error_detail(hasil)
        )
    return hasil
