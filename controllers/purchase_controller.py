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
            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
            ]
            
            query = (
                select(*purchases_table.c, *supplier_columns)
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .order_by(purchases_table.c.date.desc())
                .offset(offset)
                .limit(10)
            )
            purchases = await database.fetch_all(query)

            #Count the total number of purchases
            count_query = select(func.count()).select_from(purchases_table)
            count = await database.fetch_val(count_query)

            #Convert the result
            purchase_result = []
            for purchase in purchases:
                purchase_dict = dict(purchase)
                purchase_dict["id"] = purchase_dict.pop("id")
                purchase_dict["createdAt"] = purchase_dict.pop("createdAt")
                purchase_dict["updatedAt"] = purchase_dict.pop("updatedAt")
                purchase_dict["deletedAt"] = purchase_dict.pop("deletedAt")
                purchase_dict["createdBy"] = purchase_dict.pop("createdBy")
                purchase_dict["supplierID"] = purchase_dict.pop("supplierID")
                purchase_dict["supplier"] = {
                    "id": purchase_dict.pop("supplier_id"),
                    "name": purchase_dict.pop("supplier_name"),
                    "address": purchase_dict.pop("supplier_address"),
                    "city": purchase_dict.pop("supplier_city"),
                    "province": purchase_dict.pop("supplier_province"),
                    "prefix": purchase_dict.pop("supplier_prefix"),
                }
                purchase_result.append(purchase_dict)
            
            return {"data": purchase_result, "count": count}
        except Exception as e:
            log_error(f"Error fetching purchases: {str(e)}")
            return {"error": str(e), "status": 500} 