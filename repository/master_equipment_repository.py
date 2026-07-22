from typing import Optional, Dict, Any
from sqlalchemy import insert, select, update, func
from utils.database import database
from utils.logger_utils import log_error
from datetime import datetime as dt
from models.master_equipment_model import master_equipment_table
from schemas.master_equipment_schema import (
    MasterEquipmentCreate, MasterEquipmentUpdate, MasterEquipmentResponse,
)


class MasterEquipmentRepository:
    @staticmethod
    async def create(data: MasterEquipmentCreate) -> Dict[str, Any]:
        try:
            query = insert(master_equipment_table).values(
                **data.model_dump(exclude_none=True), isDelete=False
            )
            new_id = await database.execute(query)
            return {"message": "Equipment created successfully", "equipment_id": new_id}
        except Exception as e:
            log_error(f"Error creating equipment: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update(item_id: int, data: MasterEquipmentUpdate) -> Dict[str, Any]:
        try:
            values = data.model_dump(exclude_none=True)
            values.pop("id", None)
            values["updatedAt"] = dt.now()
            await database.execute(
                update(master_equipment_table)
                .where(master_equipment_table.c.id == item_id)
                .values(values)
            )
            return {"message": "Equipment updated successfully", "equipment_id": item_id}
        except Exception as e:
            log_error(f"Error updating equipment: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_id(item_id: int) -> Optional[MasterEquipmentResponse]:
        try:
            result = await database.fetch_one(
                select(master_equipment_table).where(
                    master_equipment_table.c.id == item_id,
                    master_equipment_table.c.isDelete == False,
                )
            )
            return MasterEquipmentResponse.model_validate(dict(result)) if result else None
        except Exception as e:
            log_error(f"Error fetching equipment by id: {str(e)}")
            raise

    @staticmethod
    async def get_paginated(page: int = 1, page_size: int = 10,
                            keyword: str = None, category: str = None) -> Dict[str, Any]:
        try:
            data_q = select(master_equipment_table).where(master_equipment_table.c.isDelete == False)
            count_q = (select(func.count()).select_from(master_equipment_table)
                       .where(master_equipment_table.c.isDelete == False))
            if keyword:
                kw = f"%{keyword}%"
                cond = (master_equipment_table.c.name.ilike(kw)
                        | master_equipment_table.c.category.ilike(kw)
                        | master_equipment_table.c.capacity.ilike(kw)
                        | master_equipment_table.c.brand.ilike(kw))
                data_q = data_q.where(cond); count_q = count_q.where(cond)
            if category:
                data_q = data_q.where(master_equipment_table.c.category == category)
                count_q = count_q.where(master_equipment_table.c.category == category)
            offset = (page - 1) * page_size
            data_q = data_q.order_by(master_equipment_table.c.name.asc()).offset(offset).limit(page_size)
            rows = await database.fetch_all(data_q)
            total = await database.fetch_val(count_q) or 0
            return {
                "data": [MasterEquipmentResponse.model_validate(dict(r)).model_dump() for r in rows],
                "count": total, "page": page, "page_size": page_size,
            }
        except Exception as e:
            log_error(f"Error fetching paginated equipment: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def soft_delete(item_id: int, deleted_by: int) -> Dict[str, Any]:
        try:
            await database.execute(
                update(master_equipment_table)
                .where(master_equipment_table.c.id == item_id)
                .values(isDelete=True, deletedBy=deleted_by, deletedAt=dt.now())
            )
            return {"message": "Equipment deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting equipment: {str(e)}")
            return {"error": str(e), "status": 500}