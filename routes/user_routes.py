from typing import Annotated
from utils.errors import error_detail
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from controllers.user_controller import UserController
from schemas.user_schema import (
    UserCreate,
    UserUpdate,
    UserResponse,
    ErrorResponse,
    PasswordChange,
)
from utils.logger_utils import log_error
from utils.auth_utils import User, get_current_user
from utils.permission import require

router = APIRouter()


@router.post("/", response_model=UserResponse)
async def create_user(
    user: UserCreate,
    current_user: Annotated[User, Depends(require("user", "create"))],
):
    result = await UserController.create_user(user.dict())
    if isinstance(result, dict) and "error" in result:
        log_error(f"Error during creating user: {str(result['error'])}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result


@router.get("/")
async def get_users(
    request: Request,
    current_user: Annotated[dict, Depends(require("user", "read"))], sortBy: str = Query(None), sortByDirection: str = Query("asc")):
    keyword = request.query_params.get("keyword")
    page = int(request.query_params.get("page", 1))
    pageSize = int(request.query_params.get("pageSize", 10))

    result = await UserController.get_users(keyword, page, pageSize, sortBy, sortByDirection)
    if "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result


@router.get("/me")
async def get_own_profile(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Profil milik sendiri.

    Sengaja TANPA `require("user", ...)`, dengan alasan yang sama seperti
    ganti sandi: melihat nama dan surel sendiri bukan tindakan administratif.

    Sebelumnya layar Pengaturan memuatnya lewat `GET /users/{id}` yang
    menuntut `user:read` — izin melihat SELURUH pengguna, dan itu level 5.
    Akibatnya seluruh pengaturan pribadi — tema, bahasa, ukuran teks, ganti
    sandi — hanya terbuka bagi pemilik sistem.

    Yang dikembalikan hanya milik penggunanya sendiri; id diambil dari token,
    bukan dari parameter, sehingga tidak dapat dipakai membaca profil orang
    lain.
    """
    hasil = await UserController.get_user_by_id(current_user["id"])
    if isinstance(hasil, dict) and "error" in hasil:
        log_error(f"Error fetching own profile: {hasil['error']}")
        raise HTTPException(status_code=hasil["status"], detail=error_detail(hasil))
    return hasil


@router.put("/me/password")
async def change_own_password(
    body: PasswordChange,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Ganti sandi milik sendiri.

    Sengaja TANPA `require("user", ...)`: ini bukan tindakan administratif.
    Menaruhnya di balik izin modul User membuat hanya admin yang bisa
    mengganti sandi — dan itulah keadaan yang justru hendak diperbaiki,
    karena berarti sandi setiap orang harus melewati admin.

    Dideklarasikan SEBELUM `/{user_id}` agar tidak ada keraguan urutan
    pencocokan rute.
    """
    result = await UserController.change_own_password(
        current_user["id"], body.currentPassword, body.newPassword
    )
    if "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    current_user: Annotated[dict, Depends(require("user", "read"))],
):
    result = await UserController.get_user_by_id(user_id)
    if "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    user: UserUpdate,
    current_user: Annotated[dict, Depends(require("user", "update"))],
):
    result = await UserController.update_user(user_id, user.dict(exclude_unset=True))
    if "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: Annotated[dict, Depends(require("user", "delete"))],
):
    result = await UserController.delete_user(user_id)
    if "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result
