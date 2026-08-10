from fastapi import APIRouter, Depends, HTTPException, Query
from controllers.asset_controller import AssetController
from schemas.asset_schema import AssetCreate, AssetUpdate
from utils.auth_utils import get_current_user
from utils.auth_utils import User
from typing import Annotated

router = APIRouter()

@router.post("/")
async def create_asset(
    asset_data: dict, 
    current_user: Annotated[User, Depends(get_current_user)]
):
    userID = current_user["id"]
    return await AssetController.create_asset(asset_data, userID)

@router.get("/")
async def get_assets(
    current_user: Annotated[User, Depends(get_current_user)],
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
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await AssetController.get_asset_by_id(asset_id)

@router.put("/{asset_id}")
async def update_asset(
    asset_id: int, 
    update_data: AssetUpdate, 
    user_id: int = Depends(get_current_user)
):
    return await AssetController.update_asset(asset_id, update_data.model_dump(), user_id)

@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await AssetController.delete_asset(asset_id)

@router.get("/search/{keyword}")
async def search_assets(
    keyword: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await AssetController.search_assets(keyword)