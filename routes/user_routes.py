from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from controllers.user_controller import UserController
from schemas.user_schema import UserCreate, UserUpdate, UserResponse, ErrorResponse
from utils.logger_utils import log_error
from utils.auth_utils import User, get_current_user

router = APIRouter()


@router.post("/", response_model=UserResponse)
async def create_user(
    user: UserCreate,
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await UserController.create_user(user.dict())
    if isinstance(result, dict) and "error" in result:
        log_error(f"Error during creating user: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result


@router.get("/")
async def get_users(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)], sortBy: str = Query(None), sortByDirection: str = Query("asc")):
    keyword = request.query_params.get("keyword")
    page = int(request.query_params.get("page", 1))
    pageSize = int(request.query_params.get("pageSize", 10))

    result = await UserController.get_users(keyword, page, pageSize, sortBy, sortByDirection)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    result = await UserController.get_user_by_id(user_id)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    user: UserUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    result = await UserController.update_user(user_id, user.dict(exclude_unset=True))
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    result = await UserController.delete_user(user_id)
    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result