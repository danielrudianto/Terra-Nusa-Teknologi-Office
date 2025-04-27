from sqlalchemy import insert, select, update, delete
from utils.database import database
from models.client_model import clients_table
from typing import Dict, List, Optional
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

class ClientController:
    @staticmethod
    async def create_client(client_data: Dict) -> Dict:
        """
        Create a new client in the database.

        Args:
            client_data (Dict): The data of the client to create.

        Returns:
            Dict: A success message with the created client ID.
        """
        log_info(f"Creating client with data: {client_data}")
        try:
            query = insert(clients_table).values(**client_data)
            client_id = await database.execute(query)
            log_info("Client created successfully with ID: %s", client_id)
            return {"message": "Client created successfully", "client_id": client_id}
        except IntegrityError as e:
            log_error(f"Integrity error: {str(e)}")
            raise HTTPException(status_code=400, detail="Client already exists.")
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def get_all_clients() -> List[Dict]:
        """
        Retrieve all clients from the database.

        Returns:
            List[Dict]: A list of all clients.
        """
        query = select(clients_table)
        return await database.fetch_all(query)

    @staticmethod
    async def get_client_by_id(client_id: int) -> Dict:
        """
        Retrieve a client by its ID.

        Args:
            client_id (int): The ID of the client to retrieve.

        Returns:
            Dict: The client data if found.

        Raises:
            HTTPException: If the client is not found.
        """
        client = await ClientController._fetch_client_by_id(client_id)
        return client

    @staticmethod
    async def update_client(client_id: int, client_data: Dict) -> Dict:
        """
        Update a client's data by its ID.

        Args:
            client_id (int): The ID of the client to update.
            client_data (Dict): The updated client data.

        Returns:
            Dict: A success message.

        Raises:
            HTTPException: If the client is not found.
        """
        await ClientController._fetch_client_by_id(client_id)  # Ensure client exists
        query = update(clients_table).where(clients_table.c.id == client_id).values(**client_data)
        try:
            await database.execute(query)
            return {"message": "Client updated successfully"}
        except Exception as e:
            log_error
            raise Exception(e)

    @staticmethod
    async def delete_client(client_id: int) -> Dict:
        """
        Delete a client by its ID.

        Args:
            client_id (int): The ID of the client to delete.

        Returns:
            Dict: A success message.

        Raises:
            HTTPException: If the client is not found.
        """
        await ClientController._fetch_client_by_id(client_id)  # Ensure client exists
        query = delete(clients_table).where(clients_table.c.id == client_id)
        try:
            await database.execute(query)
            return {"message": "Client deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting client with ID {client_id,}: {str(e)}",  )
            raise Exception(e)

    @staticmethod
    async def _fetch_client_by_id(client_id: int) -> Dict:
        """
        Helper method to fetch a client by ID and handle errors if not found.

        Args:
            client_id (int): The ID of the client to fetch.

        Returns:
            Dict: The client data if found.

        Raises:
            HTTPException: If the client is not found.
        """
        query = select(clients_table).where(clients_table.c.id == client_id)
        client = await database.fetch_one(query)
        if not client:
            log_error(f"Client with ID {client_id} not found")
            raise Exception(f"Client with ID {client_id} not found")
        return dict(client)  # Convert to dictionary for consistency