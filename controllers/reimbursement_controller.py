from sqlalchemy import insert, select, update, delete
from utils.database import database
from models.reimbursement_model import reimbursements_table, reimbursement_items_table, Reimbursement, ReimbursementItems
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
            
            ReimbursementItems.create_reimbursement_items(reimbursement_items_formatted)

            # Add items to reimbursement_items table
            if reimbursement_items:
                for item in reimbursement_items:
                    item["reimbursementID"] = reimbursement_id
                    query = insert(reimbursement_items_table).values(**item)
                    await database.execute(query)

            return {
                "message": "Reimbursement created successfully",
                "reimbursementID": reimbursement_id, 
                "name": reimbursement_name
            }
        except Exception as e:
            log_error(f"Error creating reimbursement: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_reimbursements(page: int, pageSize: int, sortBy: str = "date", sortByDirection: str = "desc"):
        """
        Get all reimbursements.
        """
        # Logic to get all reimbursements
        # This is a placeholder implementation. Replace with actual logic.
        log_info(f"Getting all reimbursements for page: {page}")
        reimbursement = await Reimbursement.get_reimbursements(page, pageSize, sortBy, sortByDirection)
        if "error" in reimbursement:
            log_error(f"Error during getting reimbursements: {reimbursement['error']}")
            return {"error": reimbursement["error"], "status": reimbursement["status"]}
        log_info(f"Reimbursements fetched successfully for page: {page}")
        return reimbursement