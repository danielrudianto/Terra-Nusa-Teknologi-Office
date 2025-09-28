from sqlalchemy import func, insert, select, update, delete, or_
from utils.database import database
from models.purchase_draft_model import PurchaseDraft
from models.reimbursement_model import Reimbursement
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

    @staticmethod
    async def get_payments_by_purchase_id(purchaseID: int):
        try:
            result = await PaymentOutgoing.get_payments_by_purchase_id(purchaseID)
            if "error" in result:
                log_error(f"Error fetching payments by purchase ID: {result['error']}")
                return {"error": result["error"], "status": result["status"]}

            return result
        except Exception as e:
            log_error(f"Error fetching payments by purchase ID: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def delete_purchase(purchaseID: int, userID: int):
        try:
            log_info(f"Attempting to delete purchase with ID: {purchaseID} by user ID: {userID}")
            # Check if the purchase exists
            purchase = await Purchase.get_purchase_by_id(purchaseID)
            if "error" in purchase:
                return {"error": purchase["error"], "status": purchase["status"]}
            
            if purchase.isDelete:
                return {"error": "Purchase is already deleted", "status": 400}
            
            result = await Purchase.delete_purchase_by_id(purchaseID, userID)
            if "error" in result:
                log_error(f"Error deleting purchase: {result['error']}")
                return {"error": result["error"], "status": result["status"]}
            
            log_info(f"Purchase with ID: {purchaseID} deleted successfully by user ID: {userID}")

            #Delete payments associated with the purchase
            payments_result = await PaymentOutgoing.delete_payment_by_purchase_id(purchaseID, userID)
            if "error" in payments_result:
                log_error(f"Error deleting payments for purchase ID {purchaseID}: {payments_result['error']}")
                return {"error": payments_result["error"], "status": payments_result["status"]}
            
            log_info(f"Payments for purchase ID {purchaseID} deleted successfully")

            log_info(f"Fetching payments history for purchase ID: {purchaseID}")

            payments_history = await PaymentOutgoing.get_payments_by_purchase_id(purchaseID)
            if "error" in payments_history:
                log_error(f"Error fetching payments history for purchase ID {purchaseID}: {payments_history['error']}")
                return {"error": payments_history["error"], "status": payments_history["status"]}
            
            log_info(f"Payments history for purchase ID {purchaseID} fetched successfully, count: {len(payments_history)}")

            #Delete mutations associated with the payments
            payment_history_result = await Mutation.delete_mutations_by_payment_ids([payment.id for payment in payments_history])
            if "error" in payment_history_result:
                log_error(f"Error deleting mutations for payments of purchase ID {purchaseID}: {payment_history_result['error']}")
                return {"error": payment_history_result["error"], "status": payment_history_result["status"]}

            return result

        except Exception as e:
            log_error(f"Error deleting purchase: {str(e)}")
            return {"error": str(e), "status": 500}