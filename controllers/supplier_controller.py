from sqlalchemy import insert, select, update, delete
from utils.database import database
from models.supplier_model import suppliers_table
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from datetime import datetime

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
        log_info(userID)
        log_info(f"Creating supplier with data: {supplier_data}")
        try:
            supplier_data["created_at"] = datetime.now()
            supplier_data["created_by"] = userID

            query = insert(suppliers_table).values(**supplier_data)
            supplier_id = await database.execute(query)
            log_info(f"Supplier created successfully with ID: {supplier_id}")
            return {"message": "Supplier created successfully", "supplier_id": supplier_id}
        except IntegrityError as e:
            log_error(f"Integrity error: {str(e)}")
            return {"error": "Client already exists.", "status": 400}
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            return {"error": "Internal server error.", "status": 500}