from typing import Dict, List, Optional
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from datetime import datetime
from schemas.client_schema import ClientCreate, ClientUpdate
from repository.client_repository import ClientRepository

class ClientController:
    @staticmethod
    async def create_client(client_data: Dict, user_id: int) -> Dict:
        """
        Create a new client in the database.
        """
        log_info(f"Creating client with data: {client_data}")
        try:
            # Add user ID to client data
            client_data["createdBy"] = user_id
            
            # Validate and create client model
            client_create = ClientCreate(**client_data)
            
            # Use repository to create client
            result = await ClientRepository.create(client_create)
            
            if "error" in result:
                log_error(f"Error creating client: {result['error']}")
                raise HTTPException(
                    status_code=result.get("status", 500), 
                    detail=result["error"]
                )
            
            log_info(f"Client created successfully with ID: {result['client_id']}")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Unexpected error creating client: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def get_clients(
        page: int, 
        page_size: int = 10, 
        sort_by: Optional[str] = None, 
        sort_direction: Optional[str] = "asc", 
        keyword: Optional[str] = None
    ) -> Dict:
        """
        Retrieve a list of clients from the database.
        """
        if page < 1:
            raise HTTPException(status_code=400, detail="Page number must be greater than 0")
        
        log_info(f"Retrieving clients with page={page}, page_size={page_size}, keyword={keyword}")

        try:
            clients = await ClientRepository.get_paginated(
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_direction=sort_direction,
                keyword=keyword
            )
            
            return clients
            
        except Exception as e:
            log_error(f"Error fetching clients: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def get_client_by_id(client_id: int) -> Dict:
        """
        Retrieve a client by its ID.
        """
        log_info(f"Fetching client with ID: {client_id}")
        try:
            client = await ClientRepository.get_by_id(client_id)
            
            if not client:
                raise HTTPException(status_code=404, detail="Client not found")
                
            return client.model_dump()
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error fetching client {client_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def validate_client_exists(client_id: int) -> Dict:
        """
        Validate that a client exists and return its data.
        """
        try:
            client = await ClientController.get_client_by_id(client_id)
            return client
        except HTTPException as e:
            log_error(f"Client with ID {client_id} not found")
            raise e

    @staticmethod
    async def update_client(client_id: int, client_data: Dict, user_id: Optional[int] = None) -> Dict:
        """
        Update a client's data by its ID.
        """
        log_info(f"Updating client {client_id} with data: {client_data}")
        try:
            # Check if client exists
            await ClientController.validate_client_exists(client_id)
            
            # Add updatedBy user ID if provided
            if user_id:
                client_data["updatedBy"] = user_id
            
            # Validate update data
            client_update = ClientUpdate(**client_data)
            
            # Update client
            result = await ClientRepository.update(client_id, client_update)
            
            if "error" in result:
                log_error(f"Error updating client: {result['error']}")
                raise HTTPException(
                    status_code=result.get("status", 500), 
                    detail=result["error"]
                )

            log_info(f"Client {client_id} updated successfully")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error updating client {client_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def delete_client(client_id: int, user_id: Optional[int] = None) -> Dict:
        """
        Soft delete a client by its ID.
        """
        log_info(f"Deleting client with ID: {client_id}")
        try:
            # Check if client exists
            await ClientController.validate_client_exists(client_id)
            
            # Soft delete client
            result = await ClientRepository.soft_delete(client_id, user_id or 0)
            
            if "error" in result:
                log_error(f"Error deleting client: {result['error']}")
                raise HTTPException(
                    status_code=result.get("status", 500), 
                    detail=result["error"]
                )

            log_info(f"Client {client_id} deleted successfully")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error deleting client {client_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def search_clients(keyword: str) -> List[Dict]:
        """
        Search clients by keyword.
        """
        log_info(f"Searching clients with keyword: {keyword}")
        try:
            clients = await ClientRepository.search_by_keyword(keyword)
            return [client.model_dump() for client in clients]
            
        except Exception as e:
            log_error(f"Error searching clients: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")