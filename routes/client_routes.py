from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from controllers.client_controller import ClientController
from models.client_model import Client
from utils.logger_utils import log_error
from utils.auth_utils import validate_token

router = APIRouter()

@router.post("/")
async def create_client(client: Client, payload: dict = Depends(validate_token)):
    try:
        userID = payload.get("user_id")
        result = await ClientController.create_client(client.model_dump(), userID)
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e  # Re-raise to return the HTTPException response

@router.get("/", dependencies=[Depends(validate_token)])
async def get_clients(payload: dict = Depends(validate_token)):
    """
    Get all clients. Requires a valid token.
    """
    return await ClientController.get_all_clients()

@router.get("/{client_id}")
async def get_client(client_id: int, payload: dict = Depends(validate_token)):
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
async def update_client(client_id: int, client: Client, payload: dict = Depends(validate_token)):
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
async def delete_client(client_id: int, payload: dict = Depends(validate_token)):
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