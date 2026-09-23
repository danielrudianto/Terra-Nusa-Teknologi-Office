"""
Rute alat SEMENTARA "tautkan pembelian lama ke CoP".

Satu berkas, satu prefix. Mencopot fiturnya = hapus berkas ini,
`repository/tautan_pembelian_repository.py`, dan satu baris `include_router`
di `routes/routes.py`.

IZIN: `certificate_of_payment:update` — sama dengan yang boleh menyunting
CoP (level 2 ke atas). Penautan tidak mengubah angka mana pun; ia menyatakan
bahwa tagihan yang sudah ada ITULAH tagihan CoP ini, dan dapat dilepas lagi.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from repository.tautan_pembelian_repository import TautanPembelianController
from utils.auth_utils import User
from utils.permission import require

router = APIRouter()


class MuatanTautan(BaseModel):
    purchaseId: int


def _bereskan(hasil: dict):
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(
            status_code=hasil.get("status", 400), detail=hasil["error"]
        )
    return hasil


@router.get("/{cop_id}/calon")
async def calon_tautan(
    cop_id: int,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "update"))],
    keyword: str = Query("", max_length=100),
):
    """Pembelian yang masih boleh ditautkan ke CoP ini."""
    return _bereskan(await TautanPembelianController.calon(cop_id, keyword.strip()))


@router.post("/{cop_id}/tautkan")
async def tautkan(
    cop_id: int,
    body: MuatanTautan,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "update"))],
):
    return _bereskan(await TautanPembelianController.tautkan(cop_id, body.purchaseId))


@router.post("/{cop_id}/lepas")
async def lepas(
    cop_id: int,
    body: MuatanTautan,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "update"))],
):
    return _bereskan(await TautanPembelianController.lepas(cop_id, body.purchaseId))
