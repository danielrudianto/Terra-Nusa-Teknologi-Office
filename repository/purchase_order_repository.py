from sqlalchemy import insert, select, func
from sqlalchemy.exc import IntegrityError
from utils.database import database
from models.purchase_order_model import purchase_orders_table
from utils.logger_utils import log_error

class PurchaseOrderRepository:
    @staticmethod
    async def get_project_purchase_order_count(project_name: str) -> int:
        """Get the count of purchase orders for a specific project."""
        try:
            query = select(func.count()).select_from(purchase_orders_table).where(
                purchase_orders_table.c.projectName == project_name,
                purchase_orders_table.c.isDelete == False
            )
            count = await database.fetch_val(query)
            return count
        except Exception as e:
            log_error(f"Error counting purchase orders for project {project_name}: {str(e)}")
            return 0

    @staticmethod
    async def create(purchase_order_data: dict):
        """Create a new purchase order in the database."""
        try:
            query = insert(purchase_orders_table).values(**purchase_order_data)
            result = await database.execute(query)
            return {"purchase_order_id": result}
        except IntegrityError as e:
            log_error(f"Integrity error while creating purchase order: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while creating purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_by_id(purchase_order_id: int):
        """Get a purchase order by its ID."""
        try:
            query = select(purchase_orders_table).where(
                purchase_orders_table.c.id == purchase_order_id,
                purchase_orders_table.c.isDelete == False
            )
            result = await database.fetch_one(query)
            
            if not result:
                return {"error": "Purchase order not found", "status": 404}
                
            return result
        except IntegrityError as e:
            log_error(f"Integrity error while fetching purchase order: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while fetching purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_all(page: int = 1, page_size: int = 10):
        """Get all purchase orders with pagination."""
        try:
            offset = (page - 1) * page_size
            
            # Main query
            query = (
                select(purchase_orders_table)
                .where(purchase_orders_table.c.isDelete == False)
                .offset(offset)
                .limit(page_size)
                .order_by(purchase_orders_table.c.createdAt.desc())
            )
            result = await database.fetch_all(query)
            
            # Count query
            count_query = select([func.count()]).select_from(purchase_orders_table).where(
                purchase_orders_table.c.isDelete == False
            )
            total_count = await database.fetch_val(count_query)
            
            return {
                "data": result,
                "count": total_count,
                "page": page,
                "page_size": page_size
            }
        except Exception as e:
            log_error(f"Unexpected error while fetching purchase orders: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update_status(purchase_order_id: int, status: str, user_id: int):
        """Update the status of a purchase order."""
        try:
            from sqlalchemy import update
            from datetime import datetime as dt
            
            query = (
                update(purchase_orders_table)
                .where(purchase_orders_table.c.id == purchase_order_id)
                .values(status=status)
            )
            await database.execute(query)
            return {"message": "Purchase order status updated successfully"}
        except IntegrityError as e:
            log_error(f"Integrity error while updating purchase order: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while updating purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def soft_delete(purchase_order_id: int, user_id: int):
        """Soft delete a purchase order."""
        try:
            from sqlalchemy import update
            from datetime import datetime as dt
            
            query = (
                update(purchase_orders_table)
                .where(purchase_orders_table.c.id == purchase_order_id)
                .values(
                    isDelete=True,
                    deletedBy=user_id,
                    deletedAt=dt.now()
                )
            )
            await database.execute(query)
            return {"message": "Purchase order deleted successfully"}
        except Exception as e:
            log_error(f"Unexpected error while deleting purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}