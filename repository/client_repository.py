from typing import List, Optional, Dict, Any
from sqlalchemy import insert, select, update, delete, func, or_, desc, asc
from utils.database import database
from utils.logger_utils import log_error
from sqlalchemy.exc import IntegrityError
from datetime import datetime as dt
from models.client_model import clients_table
from schemas.client_schema import ClientCreate, ClientUpdate, ClientResponse

class ClientRepository:
    @staticmethod
    async def create(client_data: ClientCreate) -> Dict[str, Any]:
        """
        Create a new client in the database.
        """
        try:
            query = insert(clients_table).values(
                **client_data.model_dump(exclude_none=True),
                createdAt=dt.now(),
                isDelete=False
            )
            client_id = await database.execute(query)
            return {"message": "Client created successfully", "client_id": client_id}
        except IntegrityError as e:
            log_error(f"Integrity error while creating client: {str(e)}")
            return {"error": "Client with similar data already exists", "status": 400}
        except Exception as e:
            log_error(f"Error creating client: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update(client_id: int, client_data: ClientUpdate) -> Dict[str, Any]:
        """
        Update an existing client.
        """
        try:
            update_values = client_data.model_dump(exclude_none=True)
            update_values['updatedAt'] = dt.now()
            
            query = (
                update(clients_table)
                .where(clients_table.c.id == client_id)
                .where(clients_table.c.isDelete == False)
                .values(update_values)
            )
            
            result = await database.execute(query)
            if result == 0:
                return {"error": "Client not found", "status": 404}
                
            return {"message": "Client updated successfully", "client_id": client_id}
        except IntegrityError as e:
            log_error(f"Integrity error while updating client: {str(e)}")
            return {"error": "Client with similar data already exists", "status": 400}
        except Exception as e:
            log_error(f"Error updating client: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_id(client_id: int) -> Optional[ClientResponse]:
        """
        Get a client by ID from the database.
        """
        try:
            query = select(clients_table).where(
                clients_table.c.id == client_id,
                clients_table.c.isDelete == False
            )
            result = await database.fetch_one(query)
            return ClientResponse.model_validate(dict(result)) if result else None
        except Exception as e:
            log_error(f"Error fetching client by ID: {str(e)}")
            raise

    @staticmethod
    async def get_all() -> List[ClientResponse]:
        """
        Get all active clients.
        """
        try:
            query = select(clients_table).where(clients_table.c.isDelete == False)
            result = await database.fetch_all(query)
            return [ClientResponse.model_validate(dict(row)) for row in result]
        except Exception as e:
            log_error(f"Error fetching all clients: {str(e)}")
            raise

    @staticmethod
    async def get_paginated(
        page: int = 1,
        page_size: int = 10,
        sort_by: str = None,
        sort_direction: str = "asc",
        keyword: str = None
    ) -> Dict[str, Any]:
        """
        Get paginated clients with sorting and filtering.
        """
        try:
            # Base conditions
            conditions = [clients_table.c.isDelete == False]
            
            # Add keyword search conditions
            if keyword:
                keyword_filter = f"%{keyword}%"
                search_conditions = [
                    clients_table.c.name.ilike(keyword_filter),
                    clients_table.c.address.ilike(keyword_filter),
                    clients_table.c.city.ilike(keyword_filter),
                    clients_table.c.province.ilike(keyword_filter),
                    clients_table.c.phoneNumber.ilike(keyword_filter),
                    clients_table.c.email.ilike(keyword_filter),
                ]
                conditions.append(or_(*search_conditions))

            # Build data query
            data_query = select(clients_table).where(*conditions)
            
            # Apply sorting
            if sort_by == "name":
                order_column = clients_table.c.name
            else:
                order_column = clients_table.c.createdAt
                
            if sort_direction.lower() == "desc":
                data_query = data_query.order_by(desc(order_column))
            else:
                data_query = data_query.order_by(asc(order_column))

            # Apply pagination
            offset = (page - 1) * page_size
            data_query = data_query.offset(offset).limit(page_size)

            # Build count query
            count_query = select(func.count()).select_from(clients_table).where(*conditions)

            # Execute queries
            clients_data = await database.fetch_all(data_query)
            total_count = await database.fetch_val(count_query)

            clients = [ClientResponse.model_validate(dict(row)) for row in clients_data]
            
            return {
                "data": clients,
                "count": len(clients),
                "total_count": total_count or 0,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_count + page_size - 1) // page_size if total_count else 0
            }
            
        except Exception as e:
            log_error(f"Error fetching paginated clients: {str(e)}")
            raise

    @staticmethod
    async def search_by_keyword(keyword: str) -> List[ClientResponse]:
        """
        Search clients by keyword across multiple fields.
        """
        try:
            if not keyword:
                return await ClientRepository.get_all()
                
            keyword_filter = f"%{keyword}%"
            query = select(clients_table).where(
                clients_table.c.isDelete == False
            ).where(
                clients_table.c.name.ilike(keyword_filter) |
                clients_table.c.address.ilike(keyword_filter) |
                clients_table.c.city.ilike(keyword_filter) |
                clients_table.c.province.ilike(keyword_filter) |
                clients_table.c.phoneNumber.ilike(keyword_filter) |
                clients_table.c.email.ilike(keyword_filter)
            )
            
            result = await database.fetch_all(query)
            return [ClientResponse.model_validate(dict(row)) for row in result]
        except Exception as e:
            log_error(f"Error searching clients: {str(e)}")
            raise

    @staticmethod
    async def soft_delete(client_id: int, deleted_by: int) -> Dict[str, Any]:
        """
        Soft delete a client by setting isDelete to True.
        """
        try:
            query = (
                update(clients_table)
                .where(clients_table.c.id == client_id)
                .where(clients_table.c.isDelete == False)
                .values(
                    isDelete=True,
                    deletedBy=deleted_by,
                    deletedAt=dt.now()
                )
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Client not found", "status": 404}
                
            return {"message": "Client deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting client: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def exists(client_id: int) -> bool:
        """
        Check if a client exists and is not deleted.
        """
        try:
            query = select(clients_table.c.id).where(
                clients_table.c.id == client_id,
                clients_table.c.isDelete == False
            )
            result = await database.fetch_val(query)
            return result is not None
        except Exception as e:
            log_error(f"Error checking client existence: {str(e)}")
            return False