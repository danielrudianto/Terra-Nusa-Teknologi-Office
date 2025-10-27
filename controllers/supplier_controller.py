from typing import Dict, List, Any
from utils.database import database
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from utils.meilisearch import client
from schemas.supplier_schema import SupplierCreate, SupplierUpdate, SupplierSearchDocument
from repository.supplier_repository import SupplierRepository

class SupplierController:
    @staticmethod
    async def create_supplier(supplier_data: dict, user_id: int) -> Dict[str, Any]:
        """
        Create a new supplier in the database.
        """
        log_info(f"Creating supplier with data: {supplier_data}")
        try:
            # Add user ID to supplier data
            supplier_data["createdBy"] = user_id
            supplier_data['isDelete'] = False
            
            # Validate and create supplier model
            supplier_create = SupplierCreate(**supplier_data)
            
            # Use repository to create supplier
            result = await SupplierRepository.create(supplier_create)
            
            if "error" in result:
                log_error(f"Error creating supplier: {result['error']}")
                return {"error": result["error"], "status": result["status"]}
            
            supplier_id = result["supplier_id"]
            
            # Index in Meilisearch
            await SupplierController._index_supplier_in_search(supplier_id, supplier_data)
            
            log_info(f"Supplier created successfully with ID: {supplier_id}")
            return result
            
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_supplier(supplier_id: int) -> Dict[str, Any]:
        """
        Get a supplier by ID from the database.
        """
        log_info(f"Fetching supplier with ID: {supplier_id}")
        try:
            supplier = await SupplierRepository.get_by_id(supplier_id)
            
            if not supplier:
                return {"error": "Supplier not found.", "status": 404}
                
            return supplier.model_dump()
            
        except Exception as e:
            log_error(f"Error fetching supplier: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_suppliers(keyword: str = None, page: int = 1, pageSize: int = 10) -> Dict[str, Any]:
        """
        Get suppliers from the database with Meilisearch fallback.
        """
        log_info(f"Fetching suppliers with keyword: {keyword}, page: {page}, page_size: {pageSize}")
        try:
            # Try Meilisearch first
            try:
                result = client.index("suppliers").search(
                    keyword, 
                    {"limit": pageSize, "offset": (page - 1) * pageSize}
                )

                if result["hits"]:
                    return {
                        "data": result["hits"],
                        "count": result["estimatedTotalHits"],
                        "page": page,
                        "page_size": pageSize
                    }
            except Exception as search_error:
                log_error(f"Meilisearch error, falling back to database: {str(search_error)}")
            
        except Exception as e:
            log_error(f"Error fetching suppliers: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update_supplier(supplier_data: dict, user_id: int) -> Dict[str, Any]:
        """
        Update an existing supplier in the database.
        """
        log_info(f"Updating supplier with data: {supplier_data}")
        try:
            if "id" not in supplier_data:
                return {"error": "Supplier ID is required for update", "status": 400}
                
            supplier_id = supplier_data["id"]
            
            # Check if supplier exists
            existing_supplier = await SupplierRepository.get_by_id(supplier_id)
            if not existing_supplier:
                return {"error": "Supplier not found", "status": 404}
            
            # Add updatedBy user ID
            supplier_data["updatedBy"] = user_id
            
            # Validate update data
            supplier_update = SupplierUpdate(**supplier_data)
            
            # Update supplier
            result = await SupplierRepository.update(supplier_id, supplier_update)
            
            if "error" in result:
                log_error(f"Error updating supplier: {result['error']}")
                return {"error": result["error"], "status": result["status"]}
            
            # Update search index
            await SupplierController._index_supplier_in_search(supplier_id, supplier_data)
            
            log_info(f"Supplier updated successfully with ID: {supplier_id}")
            return result
            
        except IntegrityError as e:
            log_error(f"Integrity error while updating supplier: {str(e)}")
            return {"error": "Supplier already exists.", "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while updating supplier: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def delete_supplier(supplier_id: int, user_id: int) -> Dict[str, Any]:
        """
        Soft delete a supplier.
        """
        log_info(f"Deleting supplier with ID: {supplier_id}")
        try:
            # Check if supplier exists
            existing_supplier = await SupplierRepository.get_by_id(supplier_id)
            if not existing_supplier:
                return {"error": "Supplier not found", "status": 404}
            
            # Soft delete supplier
            result = await SupplierRepository.soft_delete(supplier_id, user_id)
            
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            
            # Remove from search index
            try:
                client.index("suppliers").delete_document(supplier_id)
            except Exception as e:
                log_error(f"Error removing supplier from search index: {str(e)}")
            
            log_info(f"Supplier deleted successfully with ID: {supplier_id}")
            return result
            
        except Exception as e:
            log_error(f"Error deleting supplier: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def _index_supplier_in_search(supplier_id: int, supplier_data: dict):
        """
        Index supplier in Meilisearch.
        """
        try:
            search_doc = SupplierSearchDocument(
                id=supplier_id,
                name=f"{supplier_data['name']}, {supplier_data.get('prefix', '')}",
                address=supplier_data["address"],
                city=supplier_data["city"],
                province=supplier_data["province"],
                phoneNumber=supplier_data["phoneNumber"],
                email=supplier_data.get("email"),
                npwp=supplier_data.get("npwp"),
                itemsSold=supplier_data["itemsSold"].split(",") if supplier_data["itemsSold"] else [],
                serviceArea=supplier_data["serviceArea"].split(",") if supplier_data["serviceArea"] else []
            )
            
            client.index("suppliers").add_documents([search_doc.model_dump()])
            
        except Exception as e:
            log_error(f"Error indexing supplier in search: {str(e)}")