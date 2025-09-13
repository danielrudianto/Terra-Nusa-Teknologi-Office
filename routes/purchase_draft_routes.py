from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from utils.auth_utils import get_current_user
from models.user_model import User
from models.asset_model import Asset
from controllers.asset_controller import AssetController

router = APIRouter()

@router.get("/")
async def get_purchae_draft(page: int, pageSize: int, current_user: Annotated[User, Depends(get_current_user)]):
    return "Hi"