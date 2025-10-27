from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from controllers.client_controller import ClientController
from schemas.client_schema import ClientCreate, ClientUpdate
from utils.logger_utils import log_error
from utils.auth_utils import get_current_user
from utils.auth_utils import User

router = APIRouter()

@router.post("/")
async def create_client(
    client: ClientCreate, 
    current_user: Annotated[dict, Depends(get_current_user)]
):
    user_id = current_user["id"]
    result = await ClientController.create_client(client.model_dump(), user_id)
    return result

@router.get("/")
async def get_clients(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    keyword: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    sort_by: str = Query(None),
    sort_direction: str = Query("asc", regex="^(asc|desc)$")
):
    """
    Get all clients with pagination, sorting, and search.
    """
    result = await ClientController.get_clients(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_direction=sort_direction,
        keyword=keyword
    )
    return result

@router.get("/{client_id}")
async def get_client(
    client_id: int, 
    current_user: Annotated[dict, Depends(get_current_user)]
):
    """
    Get a specific client by ID.
    """
    result = await ClientController.get_client_by_id(client_id)
    return result

@router.put("/{client_id}")
async def update_client(
    client_id: int, 
    client: ClientUpdate, 
    current_user: Annotated[dict, Depends(get_current_user)]
):
    """
    Update a specific client by ID.
    """
    user_id = current_user["id"]
    result = await ClientController.update_client(client_id, client.model_dump(), user_id)
    return result

@router.delete("/{client_id}")
async def delete_client(
    client_id: int, 
    current_user: Annotated[dict, Depends(get_current_user)]
):
    """
    Delete a specific client by ID (soft delete).
    """
    user_id = current_user["id"]
    result = await ClientController.delete_client(client_id, user_id)
    return result

@router.get("/search/{keyword}")
async def search_clients(
    keyword: str,
    current_user: Annotated[dict, Depends(get_current_user)]
):
    """
    Search clients by keyword.
    """
    result = await ClientController.search_clients(keyword)
    return {"data": result, "count": len(result)}