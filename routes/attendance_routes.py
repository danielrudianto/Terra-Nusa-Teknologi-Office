"""
BERKAS TIDAK TERPAKAI — jangan didaftarkan sebelum diperbaiki.

Isinya salinan persis `asset_routes.py` dengan nama modul izin diganti
menjadi "attendance". Modul itu tidak ada di `constants/permission_matrix.py`,
sehingga setiap permintaannya akan selalu ditolak.

Berkas ini tidak terdaftar di `routes/routes.py`, jadi tidak berpengaruh
apa-apa sekarang. Tetapi bila suatu saat didaftarkan tanpa diperiksa,
seluruh rutenya akan menolak siapa pun tanpa sebab yang terlihat.

Bila absensi memang akan dibuat: tulis rutenya sendiri, dan daftarkan
"attendance" pada matriks izin lebih dulu.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from controllers.asset_controller import AssetController
from schemas.asset_schema import AssetCreate, AssetUpdate
from utils.auth_utils import get_current_user
from utils.permission import require
from utils.auth_utils import User
from typing import Annotated

router = APIRouter()

@router.post("/")
async def create_asset(
    asset_data: dict, 
    current_user: Annotated[User, Depends(require("attendance", "create"))]
):
    userID = current_user["id"]
    return await AssetController.create_asset(asset_data, userID)

@router.get("/")
async def get_assets(
    current_user: Annotated[User, Depends(require("attendance", "read"))],
    page: int = Query(0, ge=0),
    pageSize: int = Query(10, ge=10, le=100),
    keyword: str = Query(""),
    sortBy: str = Query(""),
    sortByDirection: str = Query("asc", regex="^(asc|desc)$")
):
    return await AssetController.get_assets(page, pageSize, keyword, sortBy, sortByDirection)

@router.get("/{asset_id}")
async def get_asset(
    asset_id: int,
    current_user: Annotated[User, Depends(require("attendance", "read"))],
):
    return await AssetController.get_asset_by_id(asset_id)

@router.put("/{asset_id}")
async def update_asset(
    asset_id: int, 
    update_data: AssetUpdate, 
    current_user: Annotated[User, Depends(require("attendance", "update"))],
):
    return await AssetController.update_asset(
        asset_id, update_data.model_dump(), current_user["id"]
    )

@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: int,
    current_user: Annotated[User, Depends(require("attendance", "delete"))],
):
    return await AssetController.delete_asset(asset_id)

@router.get("/search/{keyword}")
async def search_assets(
    keyword: str,
    current_user: Annotated[User, Depends(require("attendance", "read"))],
):
    return await AssetController.search_assets(keyword)