from typing import Dict, Any
from utils.logger_utils import log_error, log_info
from utils.meilisearch import client
from utils.meilisearch_equipment import index_document, delete_document
from schemas.master_equipment_schema import MasterEquipmentCreate, MasterEquipmentUpdate
from repository.master_equipment_repository import MasterEquipmentRepository

INDEX_NAME = "master_equipment"


class MasterEquipmentController:
    @staticmethod
    async def create_equipment(data: dict, user_id: int) -> Dict[str, Any]:
        log_info(f"Creating equipment: {data.get('name')}")
        try:
            data["createdBy"] = user_id
            payload = MasterEquipmentCreate(**data)
            result = await MasterEquipmentRepository.create(payload)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            index_document({**payload.model_dump(), "id": result["equipment_id"]})
            return result
        except Exception as e:
            log_error(f"Unexpected error creating equipment: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_equipment(item_id: int) -> Dict[str, Any]:
        try:
            item = await MasterEquipmentRepository.get_by_id(item_id)
            if not item:
                return {"error": "Equipment not found.", "status": 404}
            return item.model_dump()
        except Exception as e:
            log_error(f"Error fetching equipment: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_equipments(keyword: str = "", page: int = 1, page_size: int = 10,
                             category: str = None,
        sortBy: str = None,
        sortByDirection: str = "asc",
    ) -> Dict[str, Any]:
        try:
            try:
                params = {"limit": page_size, "offset": (page - 1) * page_size}
                if category:
                    params["filter"] = f'category = "{category}"'
                result = client.index(INDEX_NAME).search(keyword or "", params)
                return {
                    "data": result["hits"],
                    "count": result.get("estimatedTotalHits", len(result["hits"])),
                    "page": page, "page_size": page_size,
                }
            except Exception as search_error:
                log_error(f"Meilisearch error, DB fallback: {str(search_error)}")
                return await MasterEquipmentRepository.get_paginated(
                    page, page_size, keyword or None, category, sortBy, sortByDirection)
        except Exception as e:
            log_error(f"Error fetching equipments: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update_equipment(data: dict, user_id: int) -> Dict[str, Any]:
        try:
            if "id" not in data:
                return {"error": "Equipment ID is required", "status": 400}
            item_id = data["id"]
            existing = await MasterEquipmentRepository.get_by_id(item_id)
            if not existing:
                return {"error": "Equipment not found", "status": 404}
            data["updatedBy"] = user_id
            payload = MasterEquipmentUpdate(**data)
            result = await MasterEquipmentRepository.update(item_id, payload)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            merged = {**existing.model_dump(), **payload.model_dump(exclude_none=True), "id": item_id}
            index_document(merged)
            return result
        except Exception as e:
            log_error(f"Unexpected error updating equipment: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def delete_equipment(item_id: int, user_id: int) -> Dict[str, Any]:
        try:
            existing = await MasterEquipmentRepository.get_by_id(item_id)
            if not existing:
                return {"error": "Equipment not found", "status": 404}
            result = await MasterEquipmentRepository.soft_delete(item_id, user_id)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            delete_document(item_id)
            return result
        except Exception as e:
            log_error(f"Error deleting equipment: {str(e)}")
            return {"error": "Internal server error.", "status": 500}