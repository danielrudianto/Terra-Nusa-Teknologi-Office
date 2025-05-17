from sqlalchemy import func, insert, select, update, delete
from utils.database import database
from models.purchase_model import purchases_table
from models.supplier_model import suppliers_table
from utils.logger_utils import log_error, log_info
from datetime import datetime

class PurchaseController:
    @staticmethod
    async def create_purchase(purchase_data: dict, userID: int):
        purchase_data["createdBy"] = userID
        purchase_data["createdAt"] = datetime.now()
        try:
            query = insert(purchases_table).values(**purchase_data)
            purchase_id = await database.execute(query)
            return {"message": "Purchase created successfully", "purchase_id": purchase_id}
        except Exception as e:
            log_error(f"Error creating purchase: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_purchases(page: int):
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            offset = (page - 1) * 10
            query = (
                select(purchases_table, suppliers_table)
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .offset(offset)
                .limit(10)
            )
            purchases = await database.fetch_all(query)

            #Count the total number of purchases
            count_query = select(func.count()).select_from(purchases_table)
            count = await database.fetch_val(count_query)
            
            return {"data": purchases, "count": count}
        except Exception as e:
            log_error(f"Error fetching purchases: {str(e)}")
            return {"error": str(e), "status": 500}