from utils.auth_utils import get_current_user
from fastapi import APIRouter, Depends, HTTPException, Query
from controllers.asset_controller import AssetController

router = APIRouter()

@router.post("/assets")
async def create_asset(asset_data: dict, user_id: int = Depends(get_current_user)):
    return await AssetController.create_asset(asset_data, user_id)

@router.get("/assets")
async def get_assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str = Query("")
):
    return await AssetController.get_assets(page, page_size, keyword)

@router.get("/assets/{asset_id}")
async def get_asset(asset_id: int):
    return await AssetController.get_asset_by_id(asset_id)

@router.put("/assets/{asset_id}")
async def update_asset(asset_id: int, update_data: dict, user_id: int = Depends(get_current_user)):
    return await AssetController.update_asset(asset_id, update_data, user_id)

@router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: int):
    return await AssetController.delete_asset(asset_id)