from sqlalchemy import insert, select, update, delete
from utils.database import database
from models.client_model import clients_table
from typing import Dict, List, Optional
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from datetime import datetime
from models.client_model import Client

class ClientController:
    @staticmethod
    async def create_client(client_data: Dict, userID: int) -> Dict:
        """
        Create a new client in the database.

        Args:
            client_data (Dict): The data of the client to create.

        Returns:
            Dict: A success message with the created client ID.
        """
        log_info(f"Creating client with data: {client_data}")
        try:
            client_data["createdAt"] = datetime.now()
            client_data["createdBy"] = userID
            client_data["isDelete"] = False
            result = await Client.create_client(client_data)  # Validate client data using Pydantic model
            if "error" in result:
                log_error(f"Error creating client: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return result
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def get_clients(page: int, pageSize: int = 10, sortBy: Optional[str] = None, sortByDirection: Optional[str] = "asc", keyword: Optional[str] = None) -> Dict:
        """
        Retrieve a list of clients from the database.

        Args:
            page (int): The page number for pagination.
            pageSize (int): The number of clients per page.
            sortBy (Optional[str]): The field to sort by.
            sortByDirection (Optional[str]): The direction to sort (asc/desc).
            keyword (Optional[str]): A keyword to filter clients.

        Returns:
            Dict: A dictionary containing the list of clients and total count.
        """
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        log_info(f"Retrieving clients with page={page}, keyword={keyword}")

        clients = await Client.get_clients(page, pageSize, sortBy, sortByDirection, keyword)
        if "error" in clients:
            log_error(f"Error fetching clients: {clients['error']}")
            raise HTTPException(status_code=clients["status"], detail=clients["error"])
        
        return clients

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
    async def validate_client_exists(client_id: int) -> Dict:
        try:
            client = await ClientController.get_client_by_id(client_id)
            if client is None:
                return {"error": "Client not found", "status": 404}
            return client
        except HTTPException as e:
            log_error("Client with ID %d not found", client_id)
            raise e

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