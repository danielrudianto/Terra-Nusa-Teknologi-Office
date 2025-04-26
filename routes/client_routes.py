from fastapi import APIRouter, Depends
from controllers.client_controller import ClientController
from models.client_model import Client
from utils.error_handler import handle_error
from utils.auth_utils import validate_token

router = APIRouter()

@router.post("/")
async def create_client(client: Client, payload: dict = Depends(validate_token)):
    """
    Create a new client. Requires a valid token.
    """
    print(payload)
    result = await ClientController.create_client(client.model_dump())
    if "error" in result:
        handle_error(400, result["error"])
    return result

@router.get("/")
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
    result = await ClientController.get_client_by_id(client_id)
    if "error" in result:
        handle_error(400, result["error"])
    return result

@router.put("/{client_id}")
async def update_client(client_id: int, client: Client, payload: dict = Depends(validate_token)):
    """
    Update a specific client by ID. Requires a valid token.
    """
    await validate_client_exists(client_id)
    result = await ClientController.update_client(client_id, client.model_dump())
    if "error" in result:
        handle_error(400, result["error"])
    return result

@router.delete("/{client_id}")
async def delete_client(client_id: int, payload: dict = Depends(validate_token)):
    """
    Delete a specific client by ID. Requires a valid token.
    """
    await validate_client_exists(client_id)
    result = await ClientController.delete_client(client_id)
    if "error" in result:
        handle_error(400, result["error"])
    return {"message": "Client deleted successfully"}

async def validate_client_exists(client_id: int):
    client = await ClientController.get_client_by_id(client_id)
    if client is None:
        handle_error(404, "Client not found")
    if "error" in client:
        handle_error(400, client["error"])
    return client