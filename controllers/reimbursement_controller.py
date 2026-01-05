from repository.reimbursement_repository import ReimbursementRepository
from models.payment_outgoing_model import PaymentOutgoing
from schemas.reimbursement_schema import ReimbursementCreate, ReimbursementResponse
from utils.logger_utils import log_error, log_info
from datetime import datetime
from fastapi import HTTPException

class ReimbursementController:

    @staticmethod
    async def create_reimbursement(reimbursement_data: dict, userID: int):
        log_info(f"Creating reimbursement with data: {reimbursement_data}")
        try:
            reimbursement_data["createdAt"] = datetime.now()
            reimbursement_data["createdBy"] = userID
            reimbursement_items = reimbursement_data.pop("reimbursementItems", [])
            projectName = reimbursement_data["projectName"]
            reimbursement_data["isPaid"] = False
            reimbursement_data["isDelete"] = False
            reimbursement_data["isApprove"] = False

            count = await ReimbursementRepository.count_by_project_name(projectName)
            if isinstance(count, dict) and "error" in count:
                log_error(f"Error counting reimbursements by project name: {count['error']}")
                return count

            reimbursement_name = f"{count+1:03}-REIM-{projectName}-{reimbursement_data['purchaseType']}"
            reimbursement_data["name"] = reimbursement_name

            reimbursement_id = await ReimbursementRepository.create_reimbursement(reimbursement_data)
            if isinstance(reimbursement_id, dict) and "error" in reimbursement_id:
                log_error(f"Error creating reimbursement: {reimbursement_id['error']}")
                raise HTTPException(status_code=reimbursement_id["status"], detail=reimbursement_id["error"])
            
            log_info(f"Reimbursement created successfully with ID: {reimbursement_id}")
            
            if reimbursement_items:
                reimbursement_items_formatted = []
                for item in reimbursement_items:
                    item["reimbursementID"] = reimbursement_id
                    reimbursement_items_formatted.append(item)
                
                result = await ReimbursementRepository.create_reimbursement_items(reimbursement_items_formatted)
                if "error" in result:
                    log_error(f"Error creating reimbursement items: {result['error']}")
                    # Consider rolling back the reimbursement creation here

            return ReimbursementResponse(
                message="Reimbursement created successfully",
                reimbursementID=reimbursement_id,
                name=reimbursement_name
            )
        except Exception as e:
            log_error(f"Error creating reimbursement: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_reimbursements(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None):
        log_info(f"Getting reimbursements for page: {page}")
        result = await ReimbursementRepository.get_reimbursements(page, pageSize, filterObject, sortBy, sortByDirection, keyword)
        if "error" in result:
            log_error(f"Error getting reimbursements: {result['error']}")
            return result
        log_info(f"Reimbursements fetched successfully for page: {page}")
        return result

    @staticmethod
    async def get_reimbursement_by_id(reimbursementID: int):
        log_info(f"Getting reimbursement by ID: {reimbursementID}")
        reimbursement = await ReimbursementRepository.get_reimbursement_by_id(reimbursementID)
        if "error" in reimbursement:
            log_error(f"Error getting reimbursement: {reimbursement['error']}")
            return reimbursement
        
        reimbursement_items = await ReimbursementRepository.get_reimbursement_items_by_reimbursement_id(reimbursementID)
        if "error" in reimbursement_items:
            log_error(f"Error getting reimbursement items: {reimbursement_items['error']}")
            return reimbursement_items
        
        # Note: You'll need to implement PaymentOutgoing repository similarly
        payments = await PaymentOutgoing.get_payments_by_reimbursement_id(reimbursementID)
        if "error" in payments:
            log_error(f"Error getting payments: {payments['error']}")
            return payments
        
        log_info(f"Reimbursement fetched successfully for ID: {reimbursementID}")
        return {
            "reimbursement": reimbursement,
            "reimbursement_items": reimbursement_items,
            "payments": payments
        }

    @staticmethod
    async def approve_reimbursement(reimbursementID: int, userID: int):
        log_info(f"Approving reimbursement with ID: {reimbursementID}")
        try:
            reimbursement = await ReimbursementRepository.get_reimbursement_by_id(reimbursementID)
            if "error" in reimbursement:
                log_error(f"Error getting reimbursement for approval: {reimbursement['error']}")
                return reimbursement
            
            if reimbursement["isApprove"]:
                return {"message": "Reimbursement already approved", "status": 400}

            if reimbursement["isDelete"]:
                return {"message": "Reimbursement is deleted and cannot be approved", "status": 400}
        
            result = await ReimbursementRepository.approve_reimbursement_by_id(reimbursementID, userID)
            if "error" in result:
                log_error(f"Error approving reimbursement: {result['error']}")
                return result
            
            log_info(f"Reimbursement approved successfully for ID: {reimbursementID}")
            return {"message": "Reimbursement approved successfully", "reimbursementID": reimbursementID}
        except Exception as e:
            log_error(f"Error approving reimbursement: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def reject_reimbursement(reimbursementID: int, userID: int):
        log_info(f"Rejecting reimbursement with ID: {reimbursementID}")
        try:
            reimbursement = await ReimbursementRepository.get_reimbursement_by_id(reimbursementID)
            if "error" in reimbursement:
                log_error(f"Error getting reimbursement for rejection: {reimbursement['error']}")
                return reimbursement
            
            if reimbursement["isDelete"]:
                return {"message": "Reimbursement already deleted", "status": 400}
        
            result = await ReimbursementRepository.reject_reimbursement_by_id(reimbursementID, userID)
            if "error" in result:
                log_error(f"Error rejecting reimbursement: {result['error']}")
                return result
            
            log_info(f"Reimbursement rejected successfully for ID: {reimbursementID}")
            return {"message": "Reimbursement rejected successfully", "reimbursementID": reimbursementID}
        except Exception as e:
            log_error(f"Error rejecting reimbursement: {str(e)}")
            return {"error": str(e), "status": 500}