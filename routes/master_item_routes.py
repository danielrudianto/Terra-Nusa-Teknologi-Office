from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from controllers.master_item_controller import MasterItemController
from schemas.master_item_schema import (
    MasterItemCreate,
    MasterItemUpdate,
    MasterItemResponse,
    ImportResult,
)
from utils.auth_utils import get_current_user, User
from utils.permission import require

router = APIRouter()


@router.post("/")
async def create_master_item(
    item: MasterItemCreate,
    current_user: Annotated[User, Depends(require("master_item", "create"))],
):
    result = await MasterItemController.create_master_item(item.model_dump(), current_user["id"])
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result


@router.get("/")
async def get_master_items(
    current_user: Annotated[User, Depends(require("master_item", "read"))],
    keyword: str = Query("", description="Search keyword"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    purchase_type: str = Query(None, description="Filter by available purchase type, e.g. G"),
    brand: str = Query(None, description="Filter by exact brand"),
    item_type: str = Query(None, description="Filter by exact type"),
    sortBy: str = Query(None, description="Sort column: sku, brand, type"),
    sortByDirection: str = Query("asc", description="asc or desc"),
):
    result = await MasterItemController.get_master_items(
        keyword, page, page_size, purchase_type, brand, item_type, sortBy, sortByDirection
    )
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result


@router.get("/facets")
async def get_master_item_facets(
    current_user: Annotated[User, Depends(require("master_item", "read"))],
):
    """Daftar brand & type unik untuk mengisi dropdown filter."""
    result = await MasterItemController.get_facets()
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result


@router.get("/{item_id}", response_model=MasterItemResponse)
async def get_master_item(
    item_id: int,
    current_user: Annotated[User, Depends(require("master_item", "read"))],
):
    result = await MasterItemController.get_master_item(item_id)
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result


@router.put("/{item_id}")
async def update_master_item(
    item_id: int,
    item: MasterItemUpdate,
    current_user: Annotated[User, Depends(require("master_item", "update"))],
):
    payload = item.model_dump()
    payload["id"] = item_id
    result = await MasterItemController.update_master_item(payload, current_user["id"])
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result


@router.delete("/{item_id}")
async def delete_master_item(
    item_id: int,
    current_user: Annotated[User, Depends(require("master_item", "delete"))],
):
    result = await MasterItemController.delete_master_item(item_id, current_user["id"])
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result


@router.post("/import", response_model=ImportResult)
async def import_master_items(
    current_user: Annotated[User, Depends(require("master_item", "create"))],
    file: UploadFile = File(..., description="CSV file"),
):
    """Bulk import master items from a CSV file."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Hanya menerima file .csv")

    # Dibaca bertahap dengan batas ukuran: `await file.read()` tanpa batas
    # memuat seluruh berkas ke memori, sehingga satu unggahan besar bisa
    # menjatuhkan server. Nama berkas saja tidak cukup — berkas apa pun bisa
    # dinamai .csv.
    MAX_UPLOAD_BYTES = 5 * 1024 * 1024
    potongan = []
    terbaca = 0
    while True:
        bagian = await file.read(64 * 1024)
        if not bagian:
            break
        terbaca += len(bagian)
        if terbaca > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Ukuran file melebihi 5 MB.",
            )
        potongan.append(bagian)

    contents = b"".join(potongan)
    if not contents:
        raise HTTPException(status_code=400, detail="File kosong.")

    # Isi harus benar-benar teks agar tidak diproses sebagai berkas biner.
    try:
        contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File bukan CSV teks yang sah.",
        )
    result = await MasterItemController.import_csv(contents, current_user["id"])
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result