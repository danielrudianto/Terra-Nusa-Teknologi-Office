from sqlalchemy import insert, select, update, delete
from utils.database import database
from models.reimbursement_model import reimbursements_table, reimbursement_items_table
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from sqlalchemy import func

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
            reimbursement_items = reimbursement_data.pop("items", None)

            projectName = reimbursement_data["projectName"]
            
            #Count the number of reimbursement with the same project name
            count_query = select(func.count()).where(reimbursements_table.c.projectName == projectName)
            count = await database.fetch_val(count_query)

            #Create a reimbursement document name with the format
            # ###-REIM-<PROJECTNAME>-<PURCHASE_TYPE>
            reimbursement_name = f"{count+1:03}-REIM-{projectName}-{reimbursement_data['purchaseType']}"
            reimbursement_data["name"] = reimbursement_name

            query = insert(reimbursement_data).values(**reimbursement_data)
            reimbursement_id = await database.execute(query)

            # Add items to reimbursement_items table
            if reimbursement_items:
                for item in reimbursement_items:
                    item["reimbursementID"] = reimbursement_id
                    item["createdAt"] = datetime.now()
                    item["createdBy"] = userID
                    query = insert(reimbursement_items_table).values(**item)
                    await database.execute(query)

            return {"message": "Reimbursement created successfully", "user_id": userID, "reimbursement": reimbursement_data}
        except Exception as e:
            log_error(f"Error creating reimbursement: {str(e)}")
            return {"error": str(e), "status": 500}