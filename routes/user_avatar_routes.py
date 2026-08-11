from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query

from controllers.user_avatar_controller import UserAvatarController
from schemas.user_avatar_schema import UserAvatarUpdate
from utils.auth_utils import get_current_user
from utils.permission import require

router = APIRouter()


@router.get("/batch")
async def get_avatars(
    current_user: Annotated[dict, Depends(require("user_avatar", "read"))],
    ids: List[int] = Query(default=[]),
):
    """Batch fetch avatars for list views (cache first, DB for misses)."""
    result = await UserAvatarController.get_avatars(ids)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result


@router.get("/{user_id}")
async def get_avatar(
    user_id: int,
    current_user: Annotated[dict, Depends(require("user_avatar", "read"))],
):
    result = await UserAvatarController.get_avatar(user_id)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result


@router.put("/{user_id}")
async def save_avatar(
    user_id: int,
    avatar: UserAvatarUpdate,
    current_user: Annotated[dict, Depends(require("user_avatar", "update"))],
):
    # a user may only edit their own avatar unless they are an administrator.
    # current_user is a database Row, so read the fields by attribute.
    auth_level = getattr(current_user, "authenticationLevel", 1) or 1
    if current_user["id"] != user_id and auth_level < 5:
        raise HTTPException(
            status_code=403, detail="You can only change your own avatar"
        )

    result = await UserAvatarController.save_avatar(
        user_id, avatar.dict(exclude_unset=True)
    )
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result