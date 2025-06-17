from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from controllers.client_controller import ClientController
from models.client_model import Client
from utils.logger_utils import log_error
from utils.auth_utils import get_current_user

router = APIRouter()

@router.post("/")
async def create_client(client: Client, user: Annotated[dict, Depends(get_current_user)]):
    userID = user["id"]
    result = await ClientController.create_client(client.model_dump(), userID)
    if "error" in result:
        log_error(f"Error creating client: {result['error']}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.get("/")
async def get_clients(request: Request, user: Annotated[dict, Depends(get_current_user)]):
    """
    Get all clients. Requires a valid token.
    """
    keyword = request.query_params.get("keyword")
    page = int(request.query_params.get("page", 1))
    pageSize = int(request.query_params.get("pageSize", 10))
    sortBy = request.query_params.get("sortBy")
    sortByDirection = request.query_params.get("sortByDirection")

    result = await ClientController.get_clients(
        page=page,
        pageSize=pageSize,
        sortBy=sortBy,
        sortByDirection=sortByDirection,
        keyword=keyword
    )
    if "error" in result:
        log_error(f"Error fetching clients: {result['error']}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result


@router.get("/{client_id}")
async def get_client(client_id: int, payload: dict = Depends(get_current_user)):
    """
    Get a specific client by ID. Requires a valid token.
    """
    result = await ClientController.get_client_by_id(client_id)
    if "error" in result:
        log_error("Client with ID %d not found", client_id)
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result

@router.put("/{client_id}")
async def update_client(client_id: int, client: Client, payload: dict = Depends(get_current_user)):
    """
    Update a specific client by ID. Requires a valid token.
    """
    validation = await ClientController.validate_client_exists(client_id)
    if "error" in validation:
        log_error("Validation failed for client ID %d, error: %s", client_id, validation["error"])
        return HTTPException(detail=validation["error"], status_code=validation["status"])
    
    result = await ClientController.update_client(client_id, client.model_dump())
    if "error" in result:
        log_error("Failed to update client with ID %d, error: %s", client_id, result["error"])
        return HTTPException(404, detail="Client not found")
    
    return result

@router.delete("/{client_id}")
async def delete_client(client_id: int, payload: dict = Depends(get_current_user)):
    """
    Delete a specific client by ID. Requires a valid token.
    """    
    result = await ClientController.delete_client(client_id)
    if "error" in result:
        log_error("Failed to delete client with ID %d, error: %s", client_id, result["error"])
        return HTTPException(404, detail="Client not found")
    
    return {"message": "Client deleted successfully"}

