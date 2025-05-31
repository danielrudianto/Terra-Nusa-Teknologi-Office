from sqlalchemy import func, insert, select, update, delete, or_
from utils.database import database
from models.purchase_model import purchases_table, purchase_status_table, Purchase, PurchaseStatus
from models.reimbursement_model import Reimbursement
from models.payment_model import payments_table
from utils.logger_utils import log_error, log_info
from datetime import datetime

class PurchaseController:
    @staticmethod
    async def create_purchase(purchase_data: dict, userID: int):
        purchase_data["createdBy"] = userID
        purchase_data["createdAt"] = datetime.now()
        lastStatusDescription =  purchase_data.pop("lastStatusDescription")
        try:
            purchase_id = await Purchase.create_purchase(purchase_data)
            if not isinstance(purchase_id, int) and "error" in purchase_id:
                log_error(f"Error creating purchase: {purchase_id['error']}")
                return {"error": purchase_id["error"], "status": purchase_id["status"]}
            log_info(f"Purchase created successfully with ID: {purchase_id}")
            # Insert the initial status if the lastStatus is "draft"
            if lastStatusDescription == "draft":
                purchase_status_id = await PurchaseStatus.create_purchase_status({
                    "purchaseID": purchase_id,
                    "status": "draft",
                    "createdAt": purchase_data["createdAt"],
                    "description": lastStatusDescription,
                    "createdBy": userID
                })
                if "error" in purchase_status_id:
                    log_error(f"Error creating purchase status: {purchase_status_id['error']}")
                    return {"error": purchase_status_id["error"], "status": purchase_status_id["status"]}
            
            return {"message": "Purchase created successfully", "purchase_id": purchase_id}
        except Exception as e:
            log_error(f"Error creating purchase: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_purchases(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None):
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            result = await Purchase.get_purchases(page, pageSize, filterObject, sortBy, sortByDirection, keyword)
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            return result
        except Exception as e:
            log_error(f"Error fetching purchases: {str(e)}")
            return {"error": str(e), "status": 500} 

    @staticmethod
    async def get_purchase_by_id(purchaseID: int):
        result = await Purchase.get_purchase_by_id(purchaseID)
        if "error" in result:
            return {"error": result["error"], "status": result["status"]}
        return result

    @staticmethod
    async def get_payments_by_purchase_id(purchaseID: int):
        try:
            query = select(payments_table).where(payments_table.c.purchaseID == purchaseID)
            payments = await database.fetch_all(query)

            return payments
        except Exception as e:
            log_error(f"Error fetching payments by purchase ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_purchase_report_by_project(projectName: str):
        try:
            purchases = await Purchase.get_purchase_by_project(projectName)
            if "error" in purchases:
                log_error(f"Error fetching purchase report by project: {purchases['error']}")
                return {"error": purchases["error"], "status": purchases["status"]}
            
            reimbursements = await Reimbursement.get_reimbursements_by_project(projectName)
            if "error" in reimbursements:
                log_error(f"Error fetching reimbursements by project: {reimbursements['error']}")
                return {"error": reimbursements["error"], "status": reimbursements["status"]}
            
            return {
                "purchases": purchases,
                "reimbursements": reimbursements
            }
        except Exception as e:
            log_error(f"Error fetching purchase report by project: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update_status(purchaseStatus: dict, userID: int):
        try:
            purchase_id = purchaseStatus["id"]

            #Get the purchase
            query = select(purchases_table).where(purchases_table.c.id == purchase_id)
            purchase = await database.fetch_one(query)

            if not purchase:
                return {"error": "Purchase not found", "status": 404}
            if purchase["isDelete"]:
                return {"error": "Purchase is deleted", "status": 400}
            if purchase["lastStatus"] == "ready":
                return {"error": "Purchase is already ready", "status": 400}
            
            # First update the purchase status
            update_query = (
                update(purchases_table)
                .where(purchases_table.c.id == purchase_id)
                .values(
                    lastStatus="ready",
                    updatedAt=datetime.now(),
                    updatedBy=userID,
                )
            )

            await database.execute(update_query)
            # Then insert the new status
            status_query = insert(purchase_status_table).values(
                purchaseID=purchase_id,
                status="ready",
                createdAt=datetime.now(),
                description=None,
                createdBy=userID,
            )
            await database.execute(status_query)
            return {"message": "Purchase status updated successfully"}
        except Exception as e:
            log_error(f"Error updating purchase status: {str(e)}")
            return {"error": str(e), "status": 500}