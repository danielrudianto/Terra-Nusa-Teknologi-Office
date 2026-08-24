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
    current_user: Annotated[User, Depends(require("asset", "create"))]
):
    userID = current_user["id"]
    return await AssetController.create_asset(asset_data, userID)

@router.get("/")
async def get_assets(
    current_user: Annotated[User, Depends(require("asset", "read"))],
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
    current_user: Annotated[User, Depends(require("asset", "read"))],
):
    return await AssetController.get_asset_by_id(asset_id)

@router.put("/{asset_id}")
async def update_asset(
    asset_id: int, 
    update_data: AssetUpdate, 
    # `require()` mengembalikan PENGGUNANYA, bukan id-nya.
    #
    # Sebelumnya parameter ini dianotasi sebagai bilangan bulat. Anotasi itu
    # tidak menjadikannya bilangan: FastAPI tidak memeriksa — apalagi
    # mengubah — nilai yang dikembalikan sebuah dependency, sehingga
    # anotasinya hanya keterangan yang tidak pernah ditagih. Yang sampai ke
    # controller adalah `Record` utuh, dipasang sebagai `updatedBy`, lalu
    # ditolak pydantic:
    #
    #   updatedBy Input should be a valid integer [type=int_type,
    #   input_value=<databases.backends...Record object>]
    #
    # Galatnya menyebut `updatedBy` — kolom yang tidak pernah diisi siapa pun
    # dari layar — sehingga yang membacanya mencari-cari pada isian yang baru
    # saja ia ubah.
    #
    # Seluruh rute lain di berkas ini sudah memakai bentuk di bawah; hanya
    # yang ini tertinggal.
    current_user: Annotated[User, Depends(require("asset", "update"))],
):
    return await AssetController.update_asset(
        asset_id, update_data.model_dump(), current_user["id"]
    )

@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: int,
    current_user: Annotated[User, Depends(require("asset", "delete"))],
):
    return await AssetController.delete_asset(asset_id)

@router.get("/search/{keyword}")
async def search_assets(
    keyword: str,
    current_user: Annotated[User, Depends(require("asset", "read"))],
):
    return await AssetController.search_assets(keyword)