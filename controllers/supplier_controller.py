from sqlalchemy import insert, select, update, delete
from utils.database import database
from models.supplier_model import suppliers_table
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

            query = insert(suppliers_table).values(**supplier_data)
            supplier_id = await database.execute(query)
            log_info(f"Supplier created successfully with ID: {supplier_id}")
            # Add to meilisearch
            client.index("suppliers").add_documents([
                {
                    "id": supplier_id,
                    "prefix": supplier_data["prefix"],
                    "name": supplier_data["name"],
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

            return {"message": "Supplier created successfully", "supplier_id": supplier_id}
        except IntegrityError as e:
            log_error(f"Integrity error: {str(e)}")
            return {"error": "Supplier already exists.", "status": 400}
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
            query = select(suppliers_table).where(suppliers_table.c.id == supplier_id)
            supplier = await database.fetch_one(query)

            if not supplier:
                return {"message": "Supplier not found."}
            return dict(supplier)
        except Exception as e:
            log_error(f"Error fetching supplier: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_suppliers(keyword: str = None, page: int = 1):
        """
        Get suppliers from the database.

        Args:
            keyword (str): The keyword to search for.

        Returns:
            List[Dict]: A list of suppliers.
        """
        log_info(f"Fetching suppliers with keyword: {keyword}")
        try:
            result = client.index("suppliers").search(keyword, {"limit": 10, "offset": (page - 1) * 10})

            if not result["hits"]:
                return {"message": "No suppliers found."}
            return {
                "data": result["hits"],
                "count": result["estimatedTotalHits"],
            }
        except Exception as e:
            log_error(f"Error fetching suppliers: {str(e)}")
            return {"error": "Internal server error.", "status": 500}