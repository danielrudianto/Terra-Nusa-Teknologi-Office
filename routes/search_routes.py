from typing import Annotated

from fastapi import APIRouter, Depends, Query

from controllers.search_controller import SearchController
from utils.auth_utils import User, get_current_user

router = APIRouter()


@router.get("")
async def cari(
    current_user: Annotated[User, Depends(get_current_user)],
    q: str = Query("", max_length=100),
):
    """
    Pencarian global (Ctrl+K).

    TANPA `require(...)`, seperti `/dashboard/lencana`: rute ini tidak membuka
    satu modul pun. Setiap kelompok hasil memeriksa izin baca modulnya
    sendiri (SearchController), dan yang tidak berhak tidak mendapat
    kelompok itu.
    """
    return await SearchController.cari(current_user, q)
