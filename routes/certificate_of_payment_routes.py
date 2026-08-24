"""
Rute Certificate of Payment.

Divisi TIDAK diambil dari objek pengguna: yang dikembalikan `require()` tidak
memuatnya sama sekali, dan membacanya dari sana selalu menghasilkan kosong —
setiap orang engineering akan ditolak tanpa sebab yang terlihat. Ia dibaca
dari basis data lewat `_departments`, sama seperti pada purchase order.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from controllers.certificate_of_payment_controller import (
    CertificateOfPaymentController,
)
from schemas.certificate_of_payment_schema import CoPCreate, CoPUpdate
from utils.auth_utils import User
from utils.errors import ErrorCode, error_detail
from utils.logger_utils import log_error
from utils.permission import _departments, require

router = APIRouter()


def _level(user) -> int:
    return int(user["authenticationLevel"] or 1)


def _lempar_bila_galat(hasil):
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(
            status_code=hasil.get("status", 500), detail=error_detail(hasil)
        )
    return hasil


@router.get("/pagu/{purchase_order_id}")
async def pagu_spk(
    purchase_order_id: int,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "read"))],
):
    """
    Baris pekerjaan SPK beserta sisa pagunya.

    Inilah yang dibaca layar pengisi CoP: pekerjaan apa saja yang ada pada
    SPK, berapa yang sudah disertifikasi, dan berapa yang masih boleh.
    Nilai rupiahnya disaring mengikuti level pembacanya.
    """
    return _lempar_bila_galat(
        await CertificateOfPaymentController.pagu_spk(
            purchase_order_id, _level(current_user)
        )
    )


@router.get("/")
async def daftar_cop(
    current_user: Annotated[User, Depends(require("certificate_of_payment", "read"))],
    purchaseOrderID: Optional[int] = None,
    projectName: Optional[str] = None,
    createdBy: Optional[int] = None,
    page: int = Query(0, ge=0),
    pageSize: int = Query(20, ge=1, le=200),
):
    return _lempar_bila_galat(
        await CertificateOfPaymentController.get_all(
            purchase_order_id=purchaseOrderID,
            project_name=projectName,
            created_by=createdBy,
            page=page,
            page_size=pageSize,
            user_level=_level(current_user),
        )
    )


@router.get("/{cop_id}")
async def detail_cop(
    cop_id: int,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "read"))],
):
    return _lempar_bila_galat(
        await CertificateOfPaymentController.get_by_id(cop_id, _level(current_user))
    )


@router.post("/")
async def buat_cop(
    data: CoPCreate,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "create"))],
):
    """Buat certificate of payment atas sebuah SPK."""
    try:
        divisi = await _departments(current_user["id"])
        return _lempar_bila_galat(
            await CertificateOfPaymentController.create(
                data.model_dump(),
                current_user["id"],
                _level(current_user),
                divisi,
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"{__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"code": ErrorCode.INTERNAL, "message": "Internal server error."},
        )


@router.put("/{cop_id}")
async def ubah_cop(
    cop_id: int,
    data: CoPUpdate,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "update"))],
):
    divisi = await _departments(current_user["id"])
    return _lempar_bila_galat(
        await CertificateOfPaymentController.update(
            cop_id,
            data.model_dump(exclude_unset=True),
            current_user["id"],
            _level(current_user),
            divisi,
        )
    )


@router.patch("/{cop_id}/checked")
async def periksa_cop(
    cop_id: int,
    checked: bool,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "update"))],
):
    """
    Tandai CoP sudah/belum diperiksa.

    Dijaga izin `update`, bukan `approve`: memeriksa bukan menyetujui, dan
    menyamakan izinnya berarti setiap pemeriksa otomatis dapat menerbitkan
    dokumen tanpa seorang pun memutuskannya.
    """
    divisi = await _departments(current_user["id"])
    return _lempar_bila_galat(
        await CertificateOfPaymentController.set_checked(
            cop_id, checked, current_user["id"], _level(current_user), divisi
        )
    )


@router.patch("/{cop_id}/approve")
async def setujui_cop(
    cop_id: int,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "approve"))],
):
    return _lempar_bila_galat(
        await CertificateOfPaymentController.approve(
            cop_id, current_user["id"], _level(current_user)
        )
    )


@router.delete("/{cop_id}")
async def hapus_cop(
    cop_id: int,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "delete"))],
):
    return _lempar_bila_galat(
        await CertificateOfPaymentController.delete(
            cop_id, current_user["id"], _level(current_user)
        )
    )
