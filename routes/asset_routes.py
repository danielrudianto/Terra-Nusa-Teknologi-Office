from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from utils.auth_utils import get_current_user
from models.user_model import User
from models.asset_model import Asset
from controllers.asset_controller import AssetController

router = APIRouter()

@router.post("/")
async def create_asset(asset:Asset, current_user: Annotated[User, Depends(get_current_user)]):
    try:
        userID = current_user["id"]
        result = await AssetController.create_asset(asset.model_dump(), userID)
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e  # Re-raise to return the HTTPException response
    
@router.get("/")
async def fetch_asset(page: int, pageSize: int, keyword: str, current_user: Annotated[User, Depends(get_current_user)]):
    try:
        userID = current_user["id"]
        result = await Asset.get_assets(page, pageSize, keyword)
        if "error" in result:
            raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e