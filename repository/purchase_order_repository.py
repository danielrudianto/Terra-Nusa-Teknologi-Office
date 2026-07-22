import json
from datetime import datetime as dt
from sqlalchemy import insert, select, func, update
from sqlalchemy.exc import IntegrityError
from utils.database import database
from models.purchase_order_model import purchase_orders_table
from utils.logger_utils import log_error

# JSON columns that may come back as strings from the driver and should be dicts
_JSON_COLUMNS = ("customData", "billing_requirements")


def _normalize_row(row):
    """Turn a DB row into a plain dict, decoding JSON columns if they came back as strings."""
    if row is None:
        return None
    data = dict(row)
    for col in _JSON_COLUMNS:
        val = data.get(col)
        if isinstance(val, str):
            try:
                data[col] = json.loads(val)
            except (ValueError, TypeError):
                pass
    return data


class PurchaseOrderRepository:
    @staticmethod
    async def get_project_purchase_order_count(project_name: str) -> int:
        """Count non-deleted purchase orders for a specific project."""
        try:
            query = (
                select(func.count())
                .select_from(purchase_orders_table)
                .where(
                    purchase_orders_table.c.projectName == project_name,
                    purchase_orders_table.c.isDelete == False,
                )
            )
            return await database.fetch_val(query) or 0
        except Exception as e:
            log_error(f"Error counting purchase orders for project {project_name}: {str(e)}")
            return 0

    @staticmethod
    async def get_global_purchase_order_count() -> int:
        """Count all non-deleted purchase orders (used for the running PO number)."""
        try:
            query = (
                select(func.count())
                .select_from(purchase_orders_table)
                .where(purchase_orders_table.c.isDelete == False)
            )
            return await database.fetch_val(query) or 0
        except Exception as e:
            log_error(f"Error counting purchase orders: {str(e)}")
            return 0

    @staticmethod
    async def create(purchase_order_data: dict):
        """Create a new purchase order."""
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
        """Get a single non-deleted purchase order by ID."""
        try:
            query = select(purchase_orders_table).where(
                purchase_orders_table.c.id == purchase_order_id,
                purchase_orders_table.c.isDelete == False,
            )
            result = await database.fetch_one(query)
            if not result:
                return {"error": "Purchase order not found", "status": 404}
            return _normalize_row(result)
        except Exception as e:
            log_error(f"Unexpected error while fetching purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_all(page: int = 1, page_size: int = 10):
        """Get purchase orders with pagination (newest first)."""
        try:
            offset = (page - 1) * page_size
            query = (
                select(purchase_orders_table)
                .where(purchase_orders_table.c.isDelete == False)
                .order_by(purchase_orders_table.c.createdAt.desc())
                .offset(offset)
                .limit(page_size)
            )
            rows = await database.fetch_all(query)

            count_query = (
                select(func.count())
                .select_from(purchase_orders_table)
                .where(purchase_orders_table.c.isDelete == False)
            )
            total_count = await database.fetch_val(count_query) or 0

            return {
                "data": [_normalize_row(r) for r in rows],
                "count": total_count,
                "page": page,
                "page_size": page_size,
            }
        except Exception as e:
            log_error(f"Unexpected error while fetching purchase orders: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update(purchase_order_id: int, fields: dict):
        """Update editable fields of a purchase order and bump its revision."""
        try:
            if not fields:
                return {"message": "No changes"}
            query = (
                update(purchase_orders_table)
                .where(purchase_orders_table.c.id == purchase_order_id)
                .values(revision=purchase_orders_table.c.revision + 1, **fields)
            )
            await database.execute(query)
            return {"message": "Purchase order updated successfully"}
        except IntegrityError as e:
            log_error(f"Integrity error while updating purchase order: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while updating purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update_status(purchase_order_id: int, status: str, user_id: int):
        """Update only the status of a purchase order."""
        try:
            query = (
                update(purchase_orders_table)
                .where(purchase_orders_table.c.id == purchase_order_id)
                .values(status=status)
            )
            await database.execute(query)
            return {"message": "Purchase order status updated successfully"}
        except Exception as e:
            log_error(f"Unexpected error while updating purchase order status: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def approve(purchase_order_id: int, user_id: int):
        """Mark a purchase order as approved."""
        try:
            query = (
                update(purchase_orders_table)
                .where(purchase_orders_table.c.id == purchase_order_id)
                .values(
                    isApproved=True,
                    approvedBy=user_id,
                    approvedAt=dt.now(),
                    status="approved",
                )
            )
            await database.execute(query)
            return {"message": "Purchase order approved successfully"}
        except Exception as e:
            log_error(f"Unexpected error while approving purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def soft_delete(purchase_order_id: int, user_id: int):
        """Soft delete a purchase order."""
        try:
            query = (
                update(purchase_orders_table)
                .where(purchase_orders_table.c.id == purchase_order_id)
                .values(isDelete=True, deletedBy=user_id, deletedAt=dt.now())
            )
            await database.execute(query)
            return {"message": "Purchase order deleted successfully"}
        except Exception as e:
            log_error(f"Unexpected error while deleting purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}