from sqlalchemy import func, insert, select, update, delete, or_
from utils.database import database
from models.purchase_draft_model import PurchaseDraft
from models.payment_outgoing_model import PaymentOutgoing
from models.mutation_model import Mutation
from utils.logger_utils import log_error, log_info
from datetime import datetime

class PurchaseDraftController:
    @staticmethod
    async def create_purchase_draft(purchase_data: dict, userID: int):
        purchase_data["createdBy"] = userID
        purchase_data["createdAt"] = datetime.now()
        purchase_data["isDelete"] = False

        try:
            purchase_id = await PurchaseDraft.create_purchase_draft(purchase_data)
            if not isinstance(purchase_id, int) and "error" in purchase_id:
                log_error(f"Error creating purchase: {purchase_id['error']}")
                return {"error": purchase_id["error"], "status": purchase_id["status"]}
            log_info(f"Purchase draft created successfully with ID: {purchase_id}")
            
            return {"message": "Purchase draft created successfully", "purchase_draft_id": purchase_id}
        except Exception as e:
            log_error(f"Error creating purchase: {str(e)}")
            return {"error": str(e), "status": 500}
    
    @staticmethod
    async def get_purchase_draft(page: int, pageSize: int, isPending: bool, isApproved: bool, sortBy: str, sortByDirection: str, keyword: str | None):
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            result = await PurchaseDraft.get_purchase_draft(page, pageSize, isPending, isApproved, sortBy, sortByDirection, keyword)
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            return result
        except Exception as e:
            log_error(f"Error fetching purchases: {str(e)}")
            return {"error": str(e), "status": 500}         

    @staticmethod
    async def get_purchase_draft_by_id(purchaseID: int):
        result = await PurchaseDraft.get_purchase_draft_by_id(purchaseID)
        if "error" in result:
            return {"error": result["error"], "status": result["status"]}
        
        payments = await PaymentOutgoing.get_payments_by_purchase_id(purchaseID)
        if "error" in payments:
            return {"error": payments["error"], "status": payments["status"]}
        
        response = dict(result)
        
        response["payments"] = payments
        return response