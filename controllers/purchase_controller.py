from sqlalchemy import insert, select, update, delete
from utils.database import database
from models.purchase_model import purchases_table
from utils.error_handler import handle_error

class PurchaseController:
    @staticmethod
    async def create_purchase(purchase_data: dict):
        try:
            query = insert(purchases_table).values(**purchase_data)
            purchase_id = await database.execute(query)
            return {"message": "Purchase created successfully", "purchase_id": purchase_id}
        except Exception as e:
            handle_error(400, str(e))

    @staticmethod
    async def get_purchase_by_project_name(project_name: str):
        query = select(purchases_table).where(purchases_table.c.project_name == project_name)
        purchase = await database.fetch_one(query)
        if not purchase:
            handle_error(404, "Purchase not found")
        return purchase
    
    @staticmethod
    async def get_all_purchases():
        query = select(purchases_table)
        return await database.fetch_all(query)
    
    @staticmethod
    async def get_purchase_by_id(purchase_id: int):
        query = select(purchases_table).where(purchases_table.c.id == purchase_id)
        purchase = await database.fetch_one(query)
        if not purchase:
            handle_error(404, "Purchase not found")
        return purchase 