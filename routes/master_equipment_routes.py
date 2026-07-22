from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from controllers.master_equipment_controller import MasterEquipmentController
from schemas.master_equipment_schema import (
    MasterEquipmentCreate, MasterEquipmentUpdate, MasterEquipmentResponse,
)
from utils.auth_utils import get_current_user, User

router = APIRouter()


@router.post("/")
async def create_equipment(item: MasterEquipmentCreate,
                           current_user: Annotated[User, Depends(get_current_user)]):
    result = await MasterEquipmentController.create_equipment(item.model_dump(), current_user["id"])
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result


@router.get("/")
async def get_equipments(current_user: Annotated[User, Depends(get_current_user)],
                         keyword: str = Query(""), page: int = Query(1, ge=1),
                         page_size: int = Query(10, ge=1, le=100),
                         category: str = Query(None)):
    result = await MasterEquipmentController.get_equipments(keyword, page, page_size, category)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result


@router.get("/{item_id}", response_model=MasterEquipmentResponse)
async def get_equipment(item_id: int, current_user: Annotated[User, Depends(get_current_user)]):
    result = await MasterEquipmentController.get_equipment(item_id)
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result


@router.put("/{item_id}")
async def update_equipment(item_id: int, item: MasterEquipmentUpdate,
                           current_user: Annotated[User, Depends(get_current_user)]):
    payload = item.model_dump(); payload["id"] = item_id
    result = await MasterEquipmentController.update_equipment(payload, current_user["id"])
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result


@router.delete("/{item_id}")
async def delete_equipment(item_id: int, current_user: Annotated[User, Depends(get_current_user)]):
    result = await MasterEquipmentController.delete_equipment(item_id, current_user["id"])
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
    return result