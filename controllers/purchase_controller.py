from sqlalchemy import insert, select, update, delete
from utils.database import database
from models.purchase_model import purchases_table
from utils.logger_utils import log_error, log_info
from datetime import datetime

class PurchaseController:
    @staticmethod
    async def create_purchase(purchase_data: dict, userID: int):
        purchase_data["created_by"] = userID
        purchase_data["created_at"] = datetime.now()
        purchase_data["updated_at"] = None
        purchase_data["deleted_at"] = None
        purchase_data["is_delete"] = False
        try:
            query = insert(purchases_table).values(**purchase_data)
            purchase_id = await database.execute(query)
            return {"message": "Purchase created successfully", "purchase_id": purchase_id}
        except Exception as e:
            log_error(f"Error creating purchase: {str(e)}")
            return {"error": str(e), "status": 500}