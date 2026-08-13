from typing import Annotated
from utils.errors import error_detail
from fastapi import APIRouter, Depends, HTTPException, Query
from repository.audit_log_repository import AuditLogRepository
from utils.auth_utils import get_current_user, User
from utils.permission import require

router = APIRouter()


@router.get("/")
async def get_audit_logs(
    current_user: Annotated[User, Depends(require("audit_log", "read"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    entity: str = Query(None, description="Saring per entitas, mis. purchase_orders"),
    userID: int = Query(None, description="Saring per pengguna"),
    dateFrom: str = Query(None, description="Tanggal awal (YYYY-MM-DD)"),
    dateTo: str = Query(None, description="Tanggal akhir (YYYY-MM-DD)"),
):
    """Daftar aktivitas seluruh sistem."""
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