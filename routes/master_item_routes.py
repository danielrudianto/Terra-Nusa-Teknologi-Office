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

router = APIRouter()


@router.post("/")
async def create_master_item(
    item: MasterItemCreate,
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await MasterItemController.create_master_item(item.model_dump(), current_user["id"])
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result


@router.get("/")
async def get_master_items(
    current_user: Annotated[User, Depends(get_current_user)],
    keyword: str = Query("", description="Search keyword"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    purchase_type: str = Query(None, description="Filter by available purchase type, e.g. G"),
):
    result = await MasterItemController.get_master_items(keyword, page, page_size, purchase_type)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result


@router.get("/{item_id}", response_model=MasterItemResponse)
async def get_master_item(
    item_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await MasterItemController.get_master_item(item_id)
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result


@router.put("/{item_id}")
async def update_master_item(
    item_id: int,
    item: MasterItemUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
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
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await MasterItemController.delete_master_item(item_id, current_user["id"])
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result


@router.post("/import", response_model=ImportResult)
async def import_master_items(
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(..., description="CSV file"),
):
    """Bulk import master items from a CSV file."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Hanya menerima file .csv")
    contents = await file.read()
    result = await MasterItemController.import_csv(contents, current_user["id"])
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result