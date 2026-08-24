from fastapi import APIRouter, Depends, HTTPException, Request, Query
from utils.errors import error_detail
from controllers.supplier_controller import SupplierController
from schemas.supplier_schema import SupplierCreate, SupplierUpdate, SupplierBlacklistUpdate
from utils.auth_utils import get_current_user
from utils.permission import require
from typing import Annotated, Optional
from utils.auth_utils import User

router = APIRouter()

@router.post("/")
async def create_supplier(
    supplier: SupplierCreate, 
    current_user: Annotated[User, Depends(require("supplier", "create"))]
):
    user_id = current_user["id"]
    result = await SupplierController.create_supplier(supplier.model_dump(), user_id)
    if "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result


@router.get("/{supplier_id}/laporan")
async def laporan_supplier(
    supplier_id: int,
    current_user: Annotated[User, Depends(require("supplier", "read"))],
    date_from: str = Query(None, description="Tanggal pembelian sejak (YYYY-MM-DD)"),
    date_to: str = Query(None, description="Tanggal pembelian sampai (YYYY-MM-DD)"),
    project_name: str = Query(None, description="Kode proyek, persis"),
):
    """
    Laporan satu pemasok.

    Dijaga izin `supplier:read` — sama dengan melihat datanya. Yang ditampilkan
    di sini adalah rekapan dari data yang sudah boleh dilihat orang tersebut,
    bukan keterangan baru.
    """
    hasil = await SupplierController.laporan(
        supplier_id, date_from, date_to, project_name
    )
    if "error" in hasil:
        raise HTTPException(
            status_code=hasil.get("status", 500), detail=error_detail(hasil)
        )
    return hasil

@router.get("/{supplier_id}")
async def get_supplier(
    supplier_id: int, 
    current_user: Annotated[User, Depends(require("supplier", "read"))]
):
    result = await SupplierController.get_supplier(supplier_id)
    if "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result

@router.get("/")
async def get_suppliers(
    request: Request,
    current_user: Annotated[User, Depends(require("supplier", "read"))],
    keyword: str = Query(None),
    page: int = Query(0, ge=0),
    pageSize: int = Query(10, ge=10, le=100),
    isBlacklist: Optional[bool] = Query(None)
):
    try:
        result = await SupplierController.get_suppliers(keyword, page, pageSize, isBlacklist)
        if "error" in result:
            raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
        return result
    except HTTPException as e:
        raise e

@router.put("/")
async def update_supplier(
    supplier: SupplierUpdate, 
    current_user: Annotated[User, Depends(require("supplier", "update"))]
):
    user_id = current_user["id"]
    # Note: You'll need to include the ID in the update request body
    result = await SupplierController.update_supplier(supplier.model_dump(), user_id)
    if "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result

@router.delete("/{supplier_id}")
async def delete_supplier(
    supplier_id: int,
    current_user: Annotated[User, Depends(require("supplier", "delete"))]
):
    user_id = current_user["id"]
    result = await SupplierController.delete_supplier(supplier_id, user_id)
    if "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result


@router.patch("/{supplier_id}/blacklist")
async def set_supplier_blacklist(
    supplier_id: int,
    payload: SupplierBlacklistUpdate,
    current_user: Annotated[User, Depends(require("supplier", "update"))],
):
    """
    Flag / unflag a supplier as blacklisted. Warning only — it never blocks
    the supplier from being selected in a purchase or PO.
    """
    user_id = current_user["id"]
    result = await SupplierController.set_blacklist(
        supplier_id, payload.model_dump(), user_id
    )
    if "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result