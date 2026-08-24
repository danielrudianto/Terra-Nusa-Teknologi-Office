from typing import Annotated
from utils.errors import error_detail
from fastapi import APIRouter, Depends, HTTPException, Query
from controllers.master_equipment_controller import MasterEquipmentController
from schemas.master_equipment_schema import (
    MasterEquipmentCreate, MasterEquipmentUpdate, MasterEquipmentResponse,
)
from utils.auth_utils import get_current_user, User
from utils.permission import require

router = APIRouter()


@router.post("/")
async def create_equipment(item: MasterEquipmentCreate,
                           current_user: Annotated[User, Depends(require("master_equipment", "create"))]):
    result = await MasterEquipmentController.create_equipment(item.model_dump(), current_user["id"])
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=error_detail(result))
    return result


@router.get("/")
async def get_equipments(current_user: Annotated[User, Depends(require("master_equipment", "read"))],
                         keyword: str = Query(""), page: int = Query(1, ge=1),
                         page_size: int = Query(10, ge=1, le=100),
                         category: str = Query(None),
                         sortBy: str = Query(None, description="Sort column: name, category"),
                         sortByDirection: str = Query("asc", description="asc or desc")):
    result = await MasterEquipmentController.get_equipments(
        keyword, page, page_size, category, sortBy, sortByDirection
    )
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=error_detail(result))
    return result


@router.get("/{item_id}", response_model=MasterEquipmentResponse)
async def get_equipment(item_id: int, current_user: Annotated[User, Depends(require("master_equipment", "read"))]):
    result = await MasterEquipmentController.get_equipment(item_id)
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=error_detail(result))
    return result


@router.put("/{item_id}")
async def update_equipment(item_id: int, item: MasterEquipmentUpdate,
                           current_user: Annotated[User, Depends(require("master_equipment", "update"))]):
    payload = item.model_dump(); payload["id"] = item_id
    result = await MasterEquipmentController.update_equipment(payload, current_user["id"])
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=error_detail(result))
    return result


@router.delete("/{item_id}")
async def delete_equipment(item_id: int, current_user: Annotated[User, Depends(require("master_equipment", "delete"))]):
    result = await MasterEquipmentController.delete_equipment(item_id, current_user["id"])
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=error_detail(result))
    return result