from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, insert, select

from constants.department_modules import (
    DEPARTMENT_LABELS,
    DEPARTMENT_MODULES,
    UMUM,
)
from constants.permission_matrix import ACTIONS, MATRIX
from models.user_department_model import user_departments_table
from models.user_permission_model import user_permissions_table
from utils.auth_utils import User
from utils.database import database
from utils.logger_utils import log_error
from utils.permission import invalidate_permission_cache, require

router = APIRouter()

"""
Pengelolaan pengecualian akses per pengguna.

Dua hal yang berbeda diatur di sini:

  departemen  — wilayah kerja: modul apa saja yang menjadi urusannya
  izin khusus — pengecualian per aksi, mengalahkan level maupun departemen

Keduanya hanya dapat diubah oleh level 5, sama seperti modul pengguna itu
sendiri: yang boleh menambah hak orang lain adalah yang juga boleh menambah
penggunanya.
"""


class PermissionItem(BaseModel):
    module: str
    action: str
    allowed: bool
    note: Optional[str] = None


class PermissionPayload(BaseModel):
    """
    Seluruh pengecualian pengguna dikirim sekali, bukan satu per satu.

    Menyimpan per baris membuat layar dan basis data mudah berbeda ketika ada
    permintaan yang gagal di tengah; mengirim keadaan akhir menghilangkan
    kemungkinan itu.
    """

    permissions: list[PermissionItem] = []
    departments: list[str] = []


@router.get("/meta")
async def get_meta(current_user: Annotated[User, Depends(require("user", "read"))]):
    """Daftar modul, aksi, dan departemen yang dikenali sistem."""
    return {
        "modules": sorted(MATRIX.keys()),
        "actions": list(ACTIONS),
        # Disertai namanya agar layar tidak perlu menyalin daftar yang sama.
        # Disertai namanya agar layar tidak perlu menyalin daftar yang sama,
        # dan jumlah modulnya agar divisi yang belum berisi apa pun terlihat
        # sebelum ada orang ditempatkan di dalamnya.
        "departments": [
            {
                "code": d,
                "label": DEPARTMENT_LABELS.get(d, d),
                "moduleCount": len(DEPARTMENT_MODULES[d] - UMUM),
            }
            for d in DEPARTMENT_MODULES
        ],
    }


@router.get("/{user_id}")
async def get_user_access(
    user_id: int,
    current_user: Annotated[User, Depends(require("user", "read"))],
):
    """Pengecualian dan departemen yang saat ini dimiliki seorang pengguna."""
    try:
        izin = await database.fetch_all(
            select(user_permissions_table).where(
                user_permissions_table.c.userID == user_id
            )
        )
        dept = await database.fetch_all(
            select(user_departments_table).where(
                user_departments_table.c.userID == user_id
            )
        )
        return {
            "permissions": [
                {
                    "module": r["module"],
                    "action": r["action"],
                    "allowed": bool(r["allowed"]),
                    "note": r["note"],
                }
                for r in izin
            ],
            "departments": [r["department"] for r in dept],
        }
    except Exception as e:
        log_error(f"Gagal membaca akses pengguna: {str(e)}")
        raise HTTPException(status_code=500, detail="Gagal membaca akses pengguna")


@router.put("/{user_id}")
async def set_user_access(
    user_id: int,
    payload: PermissionPayload,
    current_user: Annotated[User, Depends(require("user", "update"))],
):
    """
    Ganti seluruh pengecualian dan departemen pengguna.

    Baris lama dihapus lalu ditulis ulang. Cara ini dipilih karena yang
    dikirim adalah keadaan akhir yang diinginkan: menyelisihkan baris satu per
    satu menambah kemungkinan salah tanpa memberi keuntungan apa pun pada
    jumlah data sekecil ini.
    """
    modul_sah = set(MATRIX.keys())
    aksi_sah = set(ACTIONS)
    dept_sah = set(DEPARTMENT_MODULES.keys())

    # Modul atau aksi yang tidak dikenali ditolak, bukan diabaikan: baris
    # yang salah ketik tidak akan pernah berlaku, dan diam-diam tersimpan
    # justru membuat orang mengira aksesnya sudah diberikan.
    for p in payload.permissions:
        if p.module not in modul_sah:
            raise HTTPException(400, f"Modul tidak dikenali: {p.module}")
        if p.action not in aksi_sah:
            raise HTTPException(400, f"Aksi tidak dikenali: {p.action}")
    for d in payload.departments:
        if d not in dept_sah:
            raise HTTPException(400, f"Departemen tidak dikenali: {d}")

    try:
        async with database.transaction():
            await database.execute(
                delete(user_permissions_table).where(
                    user_permissions_table.c.userID == user_id
                )
            )
            if payload.permissions:
                await database.execute_many(
                    insert(user_permissions_table),
                    [
                        {
                            "userID": user_id,
                            "module": p.module,
                            "action": p.action,
                            "allowed": p.allowed,
                            "note": p.note,
                            "createdAt": datetime.now(),
                            "createdBy": current_user["id"],
                        }
                        for p in payload.permissions
                    ],
                )

            await database.execute(
                delete(user_departments_table).where(
                    user_departments_table.c.userID == user_id
                )
            )
            if payload.departments:
                await database.execute_many(
                    insert(user_departments_table),
                    [
                        {
                            "userID": user_id,
                            "department": d,
                            "createdAt": datetime.now(),
                            "createdBy": current_user["id"],
                        }
                        for d in payload.departments
                    ],
                )

        # Tanpa ini, perubahan baru terasa setelah cache kedaluwarsa — dan
        # orang yang baru diberi akses akan mengira pemberiannya gagal.
        invalidate_permission_cache(user_id)

        from repository.audit_log_repository import AuditLogRepository

        await AuditLogRepository.record(
            entity="user_permissions",
            entityID=user_id,
            action="update",
            userID=current_user["id"],
            changes={
                "permissions": [p.dict() for p in payload.permissions],
                "departments": payload.departments,
            },
        )
        return {"user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Gagal menyimpan akses pengguna: {str(e)}")
        raise HTTPException(status_code=500, detail="Gagal menyimpan akses pengguna")
