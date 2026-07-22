from typing import Dict
from datetime import datetime as dt
from utils.logger_utils import log_info, log_error
from repository.purchase_order_repository import PurchaseOrderRepository


class PurchaseOrderController:
    @staticmethod
    async def generate_purchase_order_name(
        project_code: str = "", purchase_type: str = ""
    ) -> str:
        """
        Build the PO number using a global running sequence.
        Format: {seq:03d}-PO-{projectCode}-{purchaseType}  e.g. 025-PO-MICZ-G
        Falls back to just the 3-digit sequence when no project code is given.
        """
        try:
            count = await PurchaseOrderRepository.get_global_purchase_order_count()
            seq = f"{count + 1:03d}"
            if project_code and purchase_type:
                name = f"{seq}-PO-{project_code}-{purchase_type}"
            elif project_code:
                name = f"{seq}-PO-{project_code}"
            else:
                name = seq
            log_info(f"Generated purchase order number '{name}' (existing count: {count})")
            return name
        except Exception as e:
            log_error(f"Error generating purchase order name: {str(e)}")
            return str(int(dt.now().timestamp()))[-3:]

    @staticmethod
    async def create_purchase_order(purchase_order_data: Dict, user_id: int):
        """Create a new purchase order with an auto-generated number."""
        try:
            project_name = purchase_order_data.get("projectName", "")
            if not project_name:
                return {"error": "Project name is required", "status": 400}

            # pull out helper-only fields that are not columns
            project_code = purchase_order_data.pop("projectCode", None)
            explicit_name = purchase_order_data.pop("name", None)

            # use client-provided PO number, otherwise auto-generate
            if explicit_name:
                purchase_order_name = explicit_name
            else:
                purchase_order_name = await PurchaseOrderController.generate_purchase_order_name(
                    project_code or "", purchase_order_data.get("purchaseType", "")
                )

            # billing_requirements is NOT NULL — default to {} for the trial
            if purchase_order_data.get("billing_requirements") is None:
                purchase_order_data["billing_requirements"] = {}

            # normalize enum -> value if a raw enum slipped through
            status = purchase_order_data.get("status")
            if status is not None and hasattr(status, "value"):
                purchase_order_data["status"] = status.value

            # NOT NULL system columns (MySQL has server defaults, but set them
            # explicitly so it works regardless of driver default handling)
            purchase_order_data.setdefault("revision", 0)
            purchase_order_data.setdefault("isApproved", False)
            purchase_order_data.setdefault("isDelete", False)
            purchase_order_data["name"] = purchase_order_name
            purchase_order_data["createdBy"] = user_id
            purchase_order_data["createdAt"] = dt.now()

            result = await PurchaseOrderRepository.create(purchase_order_data)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}

            return {
                "message": "Purchase order created successfully",
                "purchase_order_id": result["purchase_order_id"],
                "purchase_order_name": purchase_order_name,
            }
        except Exception as e:
            log_error(f"Error creating purchase order: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_purchase_order_by_id(purchase_order_id: int):
        try:
            result = await PurchaseOrderRepository.get_by_id(purchase_order_id)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error fetching purchase order: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_all_purchase_orders(page: int = 1, page_size: int = 10, keyword: str = None):
        try:
            result = await PurchaseOrderRepository.get_all(page, page_size, keyword)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error fetching purchase orders: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update_purchase_order(purchase_order_id: int, fields: Dict, user_id: int):
        try:
            # drop None values so we only update provided fields
            clean = {k: v for k, v in fields.items() if v is not None}
            status = clean.get("status")
            if status is not None and hasattr(status, "value"):
                clean["status"] = status.value
            result = await PurchaseOrderRepository.update(purchase_order_id, clean)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error updating purchase order: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update_purchase_order_status(purchase_order_id: int, status: str, user_id: int):
        try:
            result = await PurchaseOrderRepository.update_status(purchase_order_id, status, user_id)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error updating purchase order status: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def approve_purchase_order(purchase_order_id: int, user_id: int):
        try:
            result = await PurchaseOrderRepository.approve(purchase_order_id, user_id)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error approving purchase order: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def delete_purchase_order(purchase_order_id: int, user_id: int):
        try:
            result = await PurchaseOrderRepository.soft_delete(purchase_order_id, user_id)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error deleting purchase order: {str(e)}")
            return {"error": str(e), "status": 500}