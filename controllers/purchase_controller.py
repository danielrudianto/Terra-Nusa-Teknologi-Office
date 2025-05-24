from sqlalchemy import func, insert, select, update, delete, or_
from utils.database import database
from models.purchase_model import purchases_table, purchase_status_table
from models.supplier_model import suppliers_table
from utils.logger_utils import log_error, log_info
from datetime import datetime

class PurchaseController:
    @staticmethod
    async def create_purchase(purchase_data: dict, userID: int):
        purchase_data["createdBy"] = userID
        purchase_data["createdAt"] = datetime.now()
        lastStatusDescription =  purchase_data.pop("lastStatusDescription")
        try:
            query = insert(purchases_table).values(**purchase_data)
            purchase_id = await database.execute(query)

            if(purchase_data["lastStatus"] == "draft"):
                status_query = insert(purchase_status_table).values(
                    purchaseID=purchase_id,
                    status=purchase_data["lastStatus"],
                    createdAt=purchase_data["createdAt"],
                    description=lastStatusDescription,
                    createdBy=userID,
                )
                await database.execute(status_query)
            return {"message": "Purchase created successfully", "purchase_id": purchase_id}
        except Exception as e:
            log_error(f"Error creating purchase: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_purchases(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str):
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            offset = (page - 1) * pageSize
            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
            ]

            conditions = [purchases_table.c.isDelete == False]

            or_conditions = []
            if filterObject.get("isDue"):
                or_conditions.append(purchases_table.c.dueDate <= datetime.now().date())
            if filterObject.get("isNotDue"):
                or_conditions.append(purchases_table.c.dueDate > datetime.now().date())

            conditions.append(or_(*or_conditions))

            or_conditions = []
            if filterObject.get("isPaid"):
                or_conditions.append(purchases_table.c.isPaid == True)
            if filterObject.get("isUnpaid"):
                or_conditions.append(purchases_table.c.isPaid == False)

            conditions.append(or_(*or_conditions))

            or_conditions = []
            if filterObject.get("isReady"):
                or_conditions.append(purchases_table.c.lastStatus == "ready")   
            if filterObject.get("isDraft"):
                or_conditions.append(purchases_table.c.lastStatus == "draft")

            conditions.append(or_(*or_conditions))

            # Sort by, using switch case
            if sortBy == "date":
                order_by = purchases_table.c.date.desc() if sortByDirection == "desc" else purchases_table.c.date
            elif sortBy == "purchaseOrderName":
                order_by = purchases_table.c.purchaseOrderName.desc() if sortByDirection == "desc" else purchases_table.c.purchaseOrderName
            elif sortBy == "dueDate":
                order_by = purchases_table.c.dueDate.desc() if sortByDirection == "desc" else purchases_table.c.dueDate
            elif sortBy == "total":
                order_by = (purchases_table.c.ppn + purchases_table.c.dpp).desc() if sortByDirection == "desc" else (purchases_table.c.ppn + purchases_table.c.dpp)
            elif sortBy == "supplier":
                order_by = suppliers_table.c.name.desc() if sortByDirection == "desc" else suppliers_table.c.name.asc()
            elif sortBy == "invoiceName":
                order_by = purchases_table.c.invoiceName.desc() if sortByDirection == "desc" else purchases_table.c.invoiceName
            else:
                order_by = purchases_table.c.date.desc()
                
            
            query = (
                select(*purchases_table.c, *supplier_columns)
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .where(*conditions)
                .order_by(order_by)
                .offset(offset)
                .limit(pageSize)
            )
            purchases = await database.fetch_all(query)

            #Count the total number of purchases
            count_query = select(func.count()).select_from(purchases_table).where(*conditions)
            count = await database.fetch_val(count_query)

            #Convert the result
            purchase_result = []
            for purchase in purchases:
                purchase_dict = dict(purchase)
                purchase_dict["id"] = purchase_dict.pop("id")
                purchase_dict["createdAt"] = purchase_dict.pop("createdAt")
                purchase_dict["updatedAt"] = purchase_dict.pop("updatedAt")
                purchase_dict["deletedAt"] = purchase_dict.pop("deletedAt")
                purchase_dict["createdBy"] = purchase_dict.pop("createdBy")
                purchase_dict["supplierID"] = purchase_dict.pop("supplierID")
                purchase_dict["supplier"] = {
                    "id": purchase_dict.pop("supplier_id"),
                    "name": purchase_dict.pop("supplier_name"),
                    "address": purchase_dict.pop("supplier_address"),
                    "city": purchase_dict.pop("supplier_city"),
                    "province": purchase_dict.pop("supplier_province"),
                    "prefix": purchase_dict.pop("supplier_prefix"),
                }
                purchase_result.append(purchase_dict)
            
            return {"data": purchase_result, "count": count}
        except Exception as e:
            log_error(f"Error fetching purchases: {str(e)}")
            return {"error": str(e), "status": 500} 

    @staticmethod
    async def get_purchase_by_id(purchaseID: int):
        try:
            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
            ]
            query = (
                select(*purchases_table.c, *supplier_columns)
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .where(purchases_table.c.id == purchaseID)
            )
            purchase = await database.fetch_one(query)

            if not purchase:
                return {"error": "Purchase not found", "status": 404}

            return purchase
        except Exception as e:
            log_error(f"Error fetching purchase by ID: {str(e)}")
            return {"error": str(e), "status": 500} 

    @staticmethod
    async def get_payments_by_purchase_id(purchaseID: int):
        try:
            query = select(purchase_status_table).where(purchase_status_table.c.purchaseID == purchaseID)
            payments = await database.fetch_all(query)

            if not payments:
                return {"error": "Payments not found", "status": 404}

            return payments
        except Exception as e:
            log_error(f"Error fetching payments by purchase ID: {str(e)}")
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