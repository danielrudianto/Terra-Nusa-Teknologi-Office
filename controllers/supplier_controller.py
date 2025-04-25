from sqlalchemy import insert, select, update, delete
from utils.database import database
from models.supplier_model import suppliers_table
from utils.error_handler import handle_error

class SupplierController:
    @staticmethod
    async def create_supplier(supplier_data: dict):
        try:
            query = insert(suppliers_table).values(**supplier_data)
            supplier_id = await database.execute(query)
            return {"message": "Supplier created successfully", "supplier_id": supplier_id}
        except Exception as e:
            handle_error(400, str(e))

    @staticmethod
    async def get_all_suppliers():
        query = select(suppliers_table)
        return await database.fetch_all(query)

    @staticmethod
    async def get_supplier_by_id(supplier_id: int):
        query = select(suppliers_table).where(suppliers_table.c.id == supplier_id)
        supplier = await database.fetch_one(query)
        if not supplier:
            handle_error(404, "Supplier not found")
        return supplier

    @staticmethod
    async def update_supplier(supplier_id: int, supplier_data: dict):
        query = update(suppliers_table).where(suppliers_table.c.id == supplier_id).values(**supplier_data)
        result = await database.execute(query)
        if not result:
            handle_error(404, "Supplier not found")
        return {"message": "Supplier updated successfully"}

    @staticmethod
    async def delete_supplier(supplier_id: int):
        query = delete(suppliers_table).where(suppliers_table.c.id == supplier_id)
        result = await database.execute(query)
        if not result:
            handle_error(404, "Supplier not found")
        return {"message": "Supplier deleted successfully"}