from sqlalchemy import insert, select, update, delete
from utils.database import database
from models.supplier_model import Supplier
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from utils.meilisearch import client

class SupplierController:
    @staticmethod
    async def create_supplier(supplier_data: dict, userID: int):
        """
        Create a new supplier in the database.

        Args:
            supplier_data (Dict): The data of the supplier to create.

        Returns:
            Dict: A success message with the created supplier ID.
        """
        log_info(f"Creating supplier with data: {supplier_data}")
        try:
            supplier_data["createdAt"] = datetime.now()
            supplier_data["createdBy"] = userID

            supplier = Supplier(**supplier_data)
            result = await supplier.create()
            if "error" in result.keys():
                log_error(f"Error creating supplier: {result['error']}")
                return {"error": result["error"], "status": result["status"]}
            
            supplierID = result["supplier_id"]
            
            client.index("suppliers").add_documents([
                {
                    "id": supplierID,
                    "name": f"{supplier_data['name']}, {supplier_data['prefix']}",
                    "address": supplier_data["address"],
                    "city": supplier_data["city"],
                    "province": supplier_data["province"],
                    "phoneNumber": supplier_data["phoneNumber"],
                    "email": supplier_data["email"],
                    "npwp": supplier_data["npwp"],
                    "items_sold": supplier_data["itemsSold"].split(","),
                    "service_area": supplier_data["serviceArea"].split(","),
                }
            ])
            
            return result
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_supplier(supplier_id: int):
        """
        Get a supplier by ID from the database.

        Args:
            supplier_id (int): The ID of the supplier to fetch.

        Returns:
            Dict: The supplier data.
        """
        log_info(f"Fetching supplier with ID: {supplier_id}")
        try:
            
            result = await Supplier.get_by_id(supplier_id)
            if "error" in result.keys():
                log_error(f"Error fetching supplier: {result['error']}")
                return {"error": result["error"], "status": result["status"]}
            if not result:
                return {"error": "Supplier not found.", "status": 404}
            supplier = Supplier(**result)
            return dict(supplier)
        except Exception as e:
            log_error(f"Error fetching supplier: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_suppliers(keyword: str = None, page: int = 1, pageSize: int = 10):
        """
        Get suppliers from the database.

        Args:
            keyword (str): The keyword to search for.

        Returns:
            List[Dict]: A list of suppliers.
        """
        log_info(f"Fetching suppliers with keyword: {keyword}")
        try:
            result = client.index("suppliers").search(keyword, {"limit": pageSize, "offset": (page - 1) * pageSize})

            if not result["hits"]:
                return {"data": [], "count": 0}
            return {
                "data": result["hits"],
                "count": result["estimatedTotalHits"],
            }
        except Exception as e:
            log_error(f"Error fetching suppliers: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
        
    @staticmethod
    async def update_supplier(supplier_data: dict, userID: int):
        """
        Update an existing supplier in the database.

        Args:
            supplier_data (Dict): The data of the supplier to update.

        Returns:
            Dict: A success message with the updated supplier ID.
        """
        log_info(f"Updating supplier with data: {supplier_data}")
        try:
            supplier_data["updatedAt"] = datetime.now()
            supplier_data["updatedBy"] = userID

            supplier = Supplier(**supplier_data)
            result = await supplier.update()
            if "error" in result.keys():
                log_error(f"Error updating supplier: {result['error']}")
                return {"error": result["error"], "status": result["status"]}
            
            client.index("suppliers").update_documents([
                {
                    "id": supplier_data["id"],
                    "name": f"{supplier_data['name']}, {supplier_data['prefix']}",
                    "address": supplier_data["address"],
                    "city": supplier_data["city"],
                    "province": supplier_data["province"],
                    "phoneNumber": supplier_data["phoneNumber"],
                    "email": supplier_data["email"],
                    "npwp": supplier_data["npwp"],
                    "items_sold": supplier_data["itemsSold"].split(","),
                    "service_area": supplier_data["serviceArea"].split(","),
                }
            ])
            
            return result
        except IntegrityError as e:
            log_error(f"Integrity error while updating supplier: {str(e)}")
            return {"error": "Supplier already exists.", "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while updating supplier: {str(e)}")
            return {"error": "Internal server error.", "status": 500}