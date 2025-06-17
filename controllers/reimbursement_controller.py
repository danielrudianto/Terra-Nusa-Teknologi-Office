from sqlalchemy import insert, select, update, delete
from utils.database import database
from models.reimbursement_model import reimbursements_table, reimbursement_items_table, Reimbursement, ReimbursementItems
from models.payment_outgoing_model import PaymentOutgoing
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from sqlalchemy import func
from fastapi import HTTPException

class ReimbursementController:
    """
    Controller class for handling reimbursement-related operations.
    """

    @staticmethod
    async def create_reimbursement(reimbursement_data: dict, userID: int):
        """
        Create a new reimbursement.
        """
        # Logic to create a reimbursement
        # This is a placeholder implementation. Replace with actual logic.
        log_info(f"Creating reimbursement with data: {reimbursement_data}")
        try:
            reimbursement_data["createdAt"] = datetime.now()
            reimbursement_data["createdBy"] = userID
            reimbursement_items = reimbursement_data.pop("reimbursementItems", None)
            projectName = reimbursement_data["projectName"]

            count = await Reimbursement.count_by_project_name(projectName)
            if not isinstance(count, int) and "error" in count:
                log_error(f"Error counting reimbursements by project name: {count['error']}")
                return {"error": count["error"], "status": count["status"]}

            #Create a reimbursement document name with the format
            # ###-REIM-<PROJECTNAME>-<PURCHASE_TYPE>
            reimbursement_name = f"{count+1:03}-REIM-{projectName}-{reimbursement_data['purchaseType']}"
            reimbursement_data["name"] = reimbursement_name

            reimbursement_id = await Reimbursement.create_reimbursement(reimbursement_data)
            if not isinstance(reimbursement_id, int) and "error" in reimbursement_id:
                log_error(f"Error on creating reimbursements", str(reimbursement_id["error"]))
                raise HTTPException(status_code=reimbursement_id["status"], detail=reimbursement_id["error"])
            log_info(f"Reimbursement created successfully with ID: {reimbursement_id}")
            
            reimbursement_items_formatted = []
            for item in reimbursement_items:
                item["reimbursementID"] = reimbursement_id
                reimbursement_items_formatted.append(item)
            
            await ReimbursementItems.create_reimbursement_items(reimbursement_items_formatted)

            # Add items to reimbursement_items table
            if reimbursement_items:
                for item in reimbursement_items:
                    item["reimbursementID"] = reimbursement_id

            return {
                "message": "Reimbursement created successfully",
                "reimbursementID": reimbursement_id, 
                "name": reimbursement_name
            }
        except Exception as e:
            log_error(f"Error creating reimbursement: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_reimbursements(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None):
        """
        Get all reimbursements.
        """
        # Logic to get all reimbursements
        # This is a placeholder implementation. Replace with actual logic.
        log_info(f"Getting reimbursements for page: {page}")
        reimbursement = await Reimbursement.get_reimbursements(page, pageSize, filterObject, sortBy, sortByDirection, keyword)
        if "error" in reimbursement:
            log_error(f"Error during getting reimbursements: {reimbursement['error']}")
            return {"error": reimbursement["error"], "status": reimbursement["status"]}
        log_info(f"Reimbursements fetched successfully for page: {page}")
        return reimbursement
    
    @staticmethod
    async def get_reimbursement_by_id(reimbursementID: int):
        """
        Get a reimbursement by ID.
        """
        # Logic to get a reimbursement by ID
        # This is a placeholder implementation. Replace with actual logic.
        log_info(f"Getting reimbursement by ID: {reimbursementID}")
        reimbursement = await Reimbursement.get_reimbursement_by_id(reimbursementID)
        if "error" in reimbursement:
            log_error(f"Error during getting reimbursement: {reimbursement['error']}")
            return {"error": reimbursement["error"], "status": reimbursement["status"]}
        
        reimbursement_items = await ReimbursementItems.get_reimbursement_items_by_reimbursement_id(reimbursementID)
        if "error" in reimbursement_items:
            log_error(f"Error during getting reimbursement items: {reimbursement_items['error']}")
            return {"error": reimbursement_items["error"], "status": reimbursement_items["status"]}
        
        payments = await PaymentOutgoing.get_payments_by_reimbursement_id(reimbursementID)
        if "error" in payments:
            log_error(f"Error during getting payments: {payments['error']}")
            return {"error": payments["error"], "status": payments["status"]}
        
        log_info(f"Reimbursement fetched successfully for ID: {reimbursementID}")
        return {
            "reimbursement": reimbursement,
            "reimbursement_items": reimbursement_items,
            "payments": payments
        }
    
    @staticmethod
    async def approve_reimbursement(reimbursementID: int, userID: int):
        """
        Approve a reimbursement.
        """
        # Logic to approve a reimbursement
        # This is a placeholder implementation. Replace with actual logic.
        log_info(f"Approving reimbursement with ID: {reimbursementID}")
        try:
            reimbursement = await Reimbursement.get_reimbursement_by_id(reimbursementID)
            if "error" in reimbursement:
                log_error(f"Error during getting reimbursement for approval: {reimbursement['error']}")
                return {"error": reimbursement["error"], "status": reimbursement["status"]}
            
            if reimbursement["isApprove"]:
                return {"message": "Reimbursement already approved", "status": 400}

            if reimbursement["isDelete"]:
                return {"message": "Reimbursement is deleted and cannot be approved", "status": 400}
        
            result = await Reimbursement.approve_reimbursement_by_id(reimbursementID, userID)
            if "error" in result:
                log_error(f"Error during approving reimbursement: {result['error']}")
                return {"error": result["error"], "status": result["status"]}
            
            log_info(f"Reimbursement approved successfully for ID: {reimbursementID}")
            return {"message": "Reimbursement approved successfully", "reimbursementID": reimbursementID}
        except Exception as e:
            log_error(f"Error approving reimbursement: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def reject_reimbursement(reimbursementID: int):
        """
        Delete a reimbursement.
        """
        # Logic to delete a reimbursement
        # This is a placeholder implementation. Replace with actual logic.
        log_info(f"Rejecting reimbursement with ID: {reimbursementID}")
        try:
            reimbursement = await Reimbursement.get_reimbursement_by_id(reimbursementID)
            if "error" in reimbursement:
                log_error(f"Error during getting reimbursement for deletion: {reimbursement['error']}")
                return {"error": reimbursement["error"], "status": reimbursement["status"]}
            
            if reimbursement["isDelete"]:
                return {"message": "Reimbursement already deleted", "status": 400}
        
            result = await Reimbursement.delete_reimbursement_by_id(reimbursementID)
            if "error" in result:
                log_error(f"Error during deleting reimbursement: {result['error']}")
                return {"error": result["error"], "status": result["status"]}
            
            log_info(f"Reimbursement deleted successfully for ID: {reimbursementID}")
            return {"message": "Reimbursement deleted successfully", "reimbursementID": reimbursementID}
        except Exception as e:
            log_error(f"Error deleting reimbursement: {str(e)}")
            return {"error": str(e), "status": 500}