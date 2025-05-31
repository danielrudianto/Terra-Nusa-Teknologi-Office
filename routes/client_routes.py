from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from controllers.client_controller import ClientController
from models.client_model import Client
from utils.logger_utils import log_error
from utils.auth_utils import get_current_user

router = APIRouter()

@router.post("/")
async def create_client(client: Client, user: Annotated[dict, Depends(get_current_user)]):
    try:
        userID = user["id"]
        result = await ClientController.create_client(client.model_dump(), userID)
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e  # Re-raise to return the HTTPException response

@router.get("/")
async def get_clients(request: Request, user: Annotated[dict, Depends(get_current_user)]):
    """
    Get all clients. Requires a valid token.
    """
    try:
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
            return HTTPException(500, detail="Internal server error")
        return result
    except Exception as e:
        log_error(f"Error fetching clients: {e}")
        return HTTPException(500, detail="Internal server error")


@router.get("/{client_id}")
async def get_client(client_id: int, payload: dict = Depends(get_current_user)):
    """
    Get a specific client by ID. Requires a valid token.
    """
    try:
        result = await ClientController.get_client_by_id(client_id)
        if "error" in result:
            log_error("Client with ID %d not found", client_id)
            return HTTPException(404, detail="Client not found")
        return result
    except Exception as e:
        log_error("Error fetching client with ID %d: %s", client_id, str(e))
        return HTTPException(500, detail="Internal server error")

@router.put("/{client_id}")
async def update_client(client_id: int, client: Client, payload: dict = Depends(get_current_user)):
    """
    Update a specific client by ID. Requires a valid token.
    """
    try:
        await validate_client_exists(client_id)
        result = await ClientController.update_client(client_id, client.model_dump())
        if "error" in result:
            log_error("Failed to update client with ID %d, error: %s", client_id, result["error"])
            return HTTPException(404, detail="Client not found")
        return result
    except Exception as e:
        log_error("Error updating client with ID %d: %s", client_id, str(e))
        return HTTPException(500, detail="Internal server error")

@router.delete("/{client_id}")
async def delete_client(client_id: int, payload: dict = Depends(get_current_user)):
    """
    Delete a specific client by ID. Requires a valid token.
    """
    # await validate_client_exists(client_id)
    # result = await ClientController.delete_client(client_id)
    # if "error" in result:
    #     handle_error(400, result["error"])
    # return {"message": "Client deleted successfully"}

async def validate_client_exists(client_id: int):
    try:
        client = await ClientController.get_client_by_id(client_id)
        if client is None:
            raise HTTPException(status_code=404, detail="Client not found")
        return client
    except HTTPException as e:
        log_error("Client with ID %d not found", client_id)
        raise e