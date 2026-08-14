from typing import Annotated
from utils.errors import ErrorCode, error_detail
from fastapi import APIRouter, Depends, HTTPException, Query
from repository.audit_log_repository import AuditLogRepository
from utils.auth_utils import get_current_user, User
from utils.permission import require

router = APIRouter()


#: Sebanyak-banyaknya nama yang boleh disaring sekaligus.
#:
#: Bukan batas teknis, melainkan batas keterbacaan: daftar yang menyaring dua
#: puluh nama sekaligus sama saja dengan tidak menyaring, dan setiap nama
#: tambahan memperbesar kueri tanpa mempersempit hasilnya.
MAKS_PENYARING_PENGGUNA = 5


@router.get("/")
async def get_audit_logs(
    current_user: Annotated[User, Depends(require("audit_log", "read"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    entity: str = Query(None, description="Saring per entitas, mis. purchase_orders"),
    userID: list[int] = Query(None, description="Saring per pengguna; boleh lebih dari satu"),
    dateFrom: str = Query(None, description="Tanggal awal (YYYY-MM-DD)"),
    dateTo: str = Query(None, description="Tanggal akhir (YYYY-MM-DD)"),
):
    """
    Daftar aktivitas.

    Di bawah level 5, yang terlihat HANYA aktivitas sendiri.

    Pembatasannya dilakukan di sini, bukan di layar: menyembunyikan penyaring
    di antarmuka tidak menghalangi siapa pun memanggil alamatnya langsung
    dengan `userID` orang lain. Nilai yang dikirim pun sengaja diabaikan,
    bukan ditolak — permintaan yang sah dari layar tetap berjalan, sementara
    yang mencoba melihat orang lain hanya memperoleh datanya sendiri.

    Jejak audit memuat perubahan slip gaji beserta angkanya. Akses gaji di
    sistem ini sengaja tidak mengikuti tangga level — hanya divisi FAT dan
    HRD yang memilikinya — sehingga membuka daftar menyeluruh untuk level 4
    akan menjadikan halaman ini pintu belakang ke data yang sudah ditutup
    bagi mereka.
    """
    level = current_user.get("authenticationLevel") or 1

    if level < 5:
        userID = [current_user["id"]]
    elif userID:
        if len(userID) > MAKS_PENYARING_PENGGUNA:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": ErrorCode.VALIDATION,
                    "message": (
                        f"At most {MAKS_PENYARING_PENGGUNA} users can be filtered at once."
                    ),
                },
            )

    result = await AuditLogRepository.get_all(
        page, page_size, entity, userID, dateFrom, dateTo
    )
    if "error" in result:
        raise HTTPException(
            status_code=result.get("status", 500), detail=error_detail(result)
        )
    return result


@router.get("/{entity}/{entity_id}")
async def get_entity_history(
    current_user: Annotated[User, Depends(require("audit_log", "read"))],
    entity: str,
    entity_id: int,
    limit: int = Query(50, ge=1, le=200),
):
    """Riwayat satu dokumen, terbaru lebih dulu."""
    result = await AuditLogRepository.get_by_entity(entity, entity_id, limit)
    if "error" in result:
        raise HTTPException(
            status_code=result.get("status", 500), detail=error_detail(result)
        )
    return result