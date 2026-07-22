from typing import List, Optional, Dict, Any
from sqlalchemy import insert, select, update, func
from sqlalchemy.exc import IntegrityError
from utils.database import database
from utils.logger_utils import log_error
from datetime import datetime as dt
from models.master_item_model import master_item_table
from schemas.master_item_schema import (
    MasterItemCreate,
    MasterItemUpdate,
    MasterItemResponse,
)


class MasterItemRepository:
    @staticmethod
    async def create(item_data: MasterItemCreate) -> Dict[str, Any]:
        try:
            query = insert(master_item_table).values(
                **item_data.model_dump(exclude_none=True),
                isDelete=False,
            )
            item_id = await database.execute(query)
            return {"message": "Master item created successfully", "master_item_id": item_id}
        except IntegrityError as e:
            log_error(f"Integrity error while creating master item: {str(e)}")
            return {"error": "SKU already exists or invalid input.", "status": 400}
        except Exception as e:
            log_error(f"Error creating master item: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update(item_id: int, item_data: MasterItemUpdate) -> Dict[str, Any]:
        try:
            values = item_data.model_dump(exclude_none=True)
            values.pop("id", None)
            values["updatedAt"] = dt.now()
            query = (
                update(master_item_table)
                .where(master_item_table.c.id == item_id)
                .values(values)
            )
            await database.execute(query)
            return {"message": "Master item updated successfully", "master_item_id": item_id}
        except IntegrityError as e:
            log_error(f"Integrity error while updating master item: {str(e)}")
            return {"error": "SKU already exists or invalid input.", "status": 400}
        except Exception as e:
            log_error(f"Error updating master item: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_id(item_id: int) -> Optional[MasterItemResponse]:
        try:
            query = select(master_item_table).where(
                master_item_table.c.id == item_id,
                master_item_table.c.isDelete == False,
            )
            result = await database.fetch_one(query)
            return MasterItemResponse.model_validate(dict(result)) if result else None
        except Exception as e:
            log_error(f"Error fetching master item by ID: {str(e)}")
            raise

    @staticmethod
    async def get_paginated(
        page: int = 1, page_size: int = 10, keyword: str = None, purchase_type: str = None
    ) -> Dict[str, Any]:
        """DB-side pagination (fallback when Meilisearch is unavailable)."""
        try:
            data_query = select(master_item_table).where(
                master_item_table.c.isDelete == False
            )
            count_query = (
                select(func.count())
                .select_from(master_item_table)
                .where(master_item_table.c.isDelete == False)
            )

            if keyword:
                kw = f"%{keyword}%"
                cond = (
                    master_item_table.c.sku.ilike(kw)
                    | master_item_table.c.description.ilike(kw)
                    | master_item_table.c.brand.ilike(kw)
                    | master_item_table.c.type.ilike(kw)
                )
                data_query = data_query.where(cond)
                count_query = count_query.where(cond)

            if purchase_type:
                type_cond = master_item_table.c.availablePurchaseType.ilike(f"%{purchase_type}%")
                data_query = data_query.where(type_cond)
                count_query = count_query.where(type_cond)

            offset = (page - 1) * page_size
            data_query = data_query.order_by(master_item_table.c.sku.asc()).offset(offset).limit(page_size)

            rows = await database.fetch_all(data_query)
            total = await database.fetch_val(count_query) or 0

            return {
                "data": [MasterItemResponse.model_validate(dict(r)).model_dump() for r in rows],
                "count": total,
                "page": page,
                "page_size": page_size,
            }
        except Exception as e:
            log_error(f"Error fetching paginated master items: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def soft_delete(item_id: int, deleted_by: int) -> Dict[str, Any]:
        try:
            query = (
                update(master_item_table)
                .where(master_item_table.c.id == item_id)
                .values(isDelete=True, deletedBy=deleted_by, deletedAt=dt.now())
            )
            await database.execute(query)
            return {"message": "Master item deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting master item: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_existing_skus(skus: List[str]) -> set:
        """Return the subset of SKUs that already exist (non-deleted)."""
        try:
            if not skus:
                return set()
            query = select(master_item_table.c.sku).where(
                master_item_table.c.sku.in_(skus),
                master_item_table.c.isDelete == False,
            )
            rows = await database.fetch_all(query)
            return {row["sku"] for row in rows}
        except Exception as e:
            log_error(f"Error checking existing SKUs: {str(e)}")
            raise

    @staticmethod
    async def bulk_create(rows: List[dict]) -> List[dict]:
        """Insert many rows; return the inserted rows (with id) for indexing."""
        inserted = []
        for r in rows:
            try:
                query = insert(master_item_table).values(**r)
                new_id = await database.execute(query)
                inserted.append({**r, "id": new_id})
            except Exception as e:
                log_error(f"Error inserting master item {r.get('sku')}: {str(e)}")
                raise
        return inserted