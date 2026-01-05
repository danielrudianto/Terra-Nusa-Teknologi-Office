from typing import Dict
from datetime import datetime as dt
from utils.logger_utils import log_info, log_error
from repository.purchase_order_repository import PurchaseOrderRepository
from fastapi import HTTPException

class PurchaseOrderController:
    @staticmethod
    async def generate_purchase_order_name(project_name: str) -> str:
        """
        Generate purchase order name in format ### based on project count.
        Example: 001, 002, 003, etc.
        """
        try:
            # Get the count of existing purchase orders for this project
            count = await PurchaseOrderRepository.get_project_purchase_order_count(project_name)
            
            # Generate the next number (count + 1) and format as 3-digit string
            next_number = count + 1
            purchase_order_name = f"{next_number:03d}"  # Formats as 001, 002, etc.
            
            log_info(f"Generated purchase order name '{purchase_order_name}' for project '{project_name}' (existing count: {count})")
            return purchase_order_name
            
        except Exception as e:
            log_error(f"Error generating purchase order name for project {project_name}: {str(e)}")
            # Fallback: use timestamp as name
            fallback_name = str(int(dt.now().timestamp()))[-3:]
            return fallback_name

    @staticmethod
    async def create_purchase_order(purchase_order_data: Dict, user_id: int):
        """
        Create a new purchase order in the database with auto-generated name.
        """
        try:
            # Generate the purchase order name based on project name
            project_name = purchase_order_data.get("projectName", "")
            if not project_name:
                return {"error": "Project name is required", "status": 400}
            
            purchase_order_name = await PurchaseOrderController.generate_purchase_order_name(project_name)
            
            # Update the purchase order data with generated name and metadata
            purchase_order_data["name"] = purchase_order_name
            purchase_order_data["createdBy"] = user_id
            purchase_order_data["createdAt"] = dt.now()
            
            log_info(f"Creating purchase order with data: {purchase_order_data}")
            
            # Create the purchase order in database
            result = await PurchaseOrderRepository.create(purchase_order_data)
            if "error" in result:
                log_error(f"Error creating purchase order: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            
            return {
                "message": "Purchase order created successfully", 
                "purchase_order_id": result["purchase_order_id"],
                "purchase_order_name": purchase_order_name
            }
        except Exception as e:
            log_error(f"Error creating purchase order: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_purchase_order_by_id(purchase_order_id: int):
        """
        Get a purchase order by its ID.
        """
        try:
            result = await PurchaseOrderRepository.get_by_id(purchase_order_id)
            if "error" in result:
                log_error(f"Error fetching purchase order: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            
            return result
        except Exception as e:
            log_error(f"Error fetching purchase order: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_all_purchase_orders(page: int = 1, page_size: int = 10):
        """
        Get all purchase orders with pagination.
        """
        try:
            result = await PurchaseOrderRepository.get_all(page, page_size)
            if "error" in result:
                log_error(f"Error fetching purchase orders: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            
            return result
        except Exception as e:
            log_error(f"Error fetching purchase orders: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update_purchase_order_status(purchase_order_id: int, status: str, user_id: int):
        """
        Update the status of a purchase order.
        """
        try:
            result = await PurchaseOrderRepository.update_status(purchase_order_id, status, user_id)
            if "error" in result:
                log_error(f"Error updating purchase order status: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            
            return result
        except Exception as e:
            log_error(f"Error updating purchase order status: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def delete_purchase_order(purchase_order_id: int, user_id: int):
        """
        Soft delete a purchase order.
        """
        try:
            result = await PurchaseOrderRepository.soft_delete(purchase_order_id, user_id)
            if "error" in result:
                log_error(f"Error deleting purchase order: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            
            return result
        except Exception as e:
            log_error(f"Error deleting purchase order: {str(e)}")
            return {"error": str(e), "status": 500}