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
            reimbursement_items = reimbursement_data.pop("reimbursementItems", None)

            projectName = reimbursement_data["projectName"]
            
            #Count the number of reimbursement with the same project name
            count_query = select(func.count()).where(reimbursements_table.c.projectName == projectName)
            count = await database.fetch_val(count_query)

            #Create a reimbursement document name with the format
            # ###-REIM-<PROJECTNAME>-<PURCHASE_TYPE>
            reimbursement_name = f"{count+1:03}-REIM-{projectName}-{reimbursement_data['purchaseType']}"
            reimbursement_data["name"] = reimbursement_name

            query = insert(reimbursements_table).values(**reimbursement_data)
            reimbursement_id = await database.execute(query)

            # Add items to reimbursement_items table
            if reimbursement_items:
                for item in reimbursement_items:
                    item["reimbursementID"] = reimbursement_id
                    query = insert(reimbursement_items_table).values(**item)
                    await database.execute(query)

            return {"message": "Reimbursement created successfully", "user_id": userID, "reimbursementID": reimbursement_id}
        except Exception as e:
            log_error(f"Error creating reimbursement: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_reimbursements(page: int):
        """
        Get all reimbursements.
        """
        # Logic to get all reimbursements
        # This is a placeholder implementation. Replace with actual logic.
        log_info(f"Getting all reimbursements for page: {page}")
        try:
            # "SELECT reimbursements.*, a.amount FROM reimbursements LEFT JOIN (SELECT reimbursementID, SUM(amount) as amount FROM reimbursement_items GROUP BY reimbursementID) a ON reimbursements.id = a.reimbursementID ORDER BY date DESC LIMIT 10 OFFSET (page - 1) * 10"
            amount_subq = (
                select(
                    reimbursement_items_table.c.reimbursementID,
                    func.sum(reimbursement_items_table.c.amount).label("amount")
                )
                .group_by(reimbursement_items_table.c.reimbursementID)
            ).subquery()

            query = (
                select(
                    reimbursements_table,
                    amount_subq.c.amount
                )
                .select_from(
                    reimbursements_table.outerjoin(
                        amount_subq, reimbursements_table.c.id == amount_subq.c.reimbursementID
                    )
                )
                .order_by(reimbursements_table.c.date.desc())
                .limit(10)
                .offset((page - 1) * 10)
            )

            reimbursements = await database.fetch_all(query)

            #Count the total number of purchases
            count_query = select(func.count()).select_from(reimbursements_table)
            count = await database.fetch_val(count_query)

            return {"data": reimbursements, "count": count}
        except Exception as e:
            log_error(f"Error getting reimbursements: {str(e)}")
            return {"error": str(e), "status": 500}