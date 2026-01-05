from sqlalchemy import select, func, or_, insert, update
from utils.database import database
from utils.logger_utils import log_error
from models.purchase_model import purchases_table, purchase_status_table
from models.supplier_model import suppliers_table
from datetime import datetime as dt

class PurchaseRepository:
    @staticmethod
    async def create(purchase_data: dict):
        """
        Create a new purchase in the database.
        """
        try:
            query = insert(purchases_table).values(purchase_data)
            purchase_id = await database.execute(query)
            return purchase_id
        except Exception as e:
            log_error(f"Error creating purchase: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_all(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None):
        """
        Retrieve a list of purchases from the database.
        """
        if page < 0:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            offset = (page) * pageSize

            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
            ]

            conditions = [purchases_table.c.isDelete == False]

            # Keyword search conditions
            or_conditions = []
            if keyword is not None and keyword != "":
                or_conditions.append(purchases_table.c.purchaseOrderName.ilike(f"%{keyword}%"))
                or_conditions.append(purchases_table.c.invoiceName.ilike(f"%{keyword}%"))
                or_conditions.append(purchases_table.c.receiptName.ilike(f"%{keyword}%"))
                or_conditions.append(purchases_table.c.taxInvoiceName.ilike(f"%{keyword}%"))
                or_conditions.append(suppliers_table.c.name.ilike(f"%{keyword}%"))
            
            if or_conditions:
                conditions.append(or_(*or_conditions))

            # Due date filter conditions
            due_or_conditions = []
            if filterObject.get("isDue"):
                due_or_conditions.append(purchases_table.c.dueDate <= dt.now().date())
            if filterObject.get("isNotDue"):
                due_or_conditions.append(purchases_table.c.dueDate > dt.now().date())
            
            if due_or_conditions:
                conditions.append(or_(*due_or_conditions))

            # Payment status filter conditions
            payment_or_conditions = []
            if filterObject.get("isPaid"):
                payment_or_conditions.append(purchases_table.c.isPaid == True)
            if filterObject.get("isUnpaid"):
                payment_or_conditions.append(purchases_table.c.isPaid == False)
            
            if payment_or_conditions:
                conditions.append(or_(*payment_or_conditions))

            # Status filter conditions
            status_or_conditions = []
            if filterObject.get("isReady"):
                status_or_conditions.append(purchases_table.c.lastStatus == "ready")
            if filterObject.get("isDraft"):
                status_or_conditions.append(purchases_table.c.lastStatus == "draft")
            
            if status_or_conditions:
                conditions.append(or_(*status_or_conditions))

            # Sort by
            if sortBy == "date":
                order_by = purchases_table.c.date.desc() if sortByDirection == "desc" else purchases_table.c.date.asc()
            elif sortBy == "purchaseOrderName":
                order_by = purchases_table.c.purchaseOrderName.desc() if sortByDirection == "desc" else purchases_table.c.purchaseOrderName.asc()
            elif sortBy == "dueDate":
                order_by = purchases_table.c.dueDate.desc() if sortByDirection == "desc" else purchases_table.c.dueDate.asc()
            elif sortBy == "total":
                order_by = (purchases_table.c.ppn + purchases_table.c.dpp).desc() if sortByDirection == "desc" else (purchases_table.c.ppn + purchases_table.c.dpp).asc()
            elif sortBy == "supplier":
                order_by = suppliers_table.c.name.desc() if sortByDirection == "desc" else suppliers_table.c.name.asc()
            elif sortBy == "invoiceName":
                order_by = purchases_table.c.invoiceName.desc() if sortByDirection == "desc" else purchases_table.c.invoiceName.asc()
            elif sortBy == "project":
                order_by = purchases_table.c.projectName.desc() if sortByDirection == "desc" else purchases_table.c.projectName.asc()
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

            # Count the total number of purchases
            count_query = (
                select(func.count())
                .select_from(purchases_table.join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id))
                .where(*conditions)
            )
            count = await database.fetch_val(count_query)

            # Convert the result
            purchase_result = []
            for purchase in purchases:
                purchase_dict = dict(purchase)
                purchase_dict["supplier"] = {
                    "id": purchase_dict["supplier_id"],
                    "name": purchase_dict["supplier_name"],
                    "address": purchase_dict["supplier_address"],
                    "city": purchase_dict["supplier_city"],
                    "province": purchase_dict["supplier_province"],
                    "prefix": purchase_dict["supplier_prefix"],
                }
                # Remove individual supplier fields
                for field in ["supplier_id", "supplier_name", "supplier_address", "supplier_city", "supplier_province", "supplier_prefix"]:
                    purchase_dict.pop(field, None)
                purchase_result.append(purchase_dict)

            return {"data": purchase_result, "count": count}
        except Exception as e:
            log_error(f"Error fetching purchases: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def check_exists(invoiceName: str, purchaseOrderName: str):
        """
        Check if a purchase with the given invoice name and purchase order name exists.
        """
        try:
            conditions = [
                purchases_table.c.isDelete == False,
                purchases_table.c.invoiceName == invoiceName,
                purchases_table.c.purchaseOrderName == purchaseOrderName
            ]
            
            query = (
                select(func.count())
                .select_from(purchases_table.join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id))
                .where(*conditions)
            )
            count = await database.fetch_val(query)
            return {"exists": count > 0}
        except Exception as e:
            log_error(f"Error checking purchase: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_id(purchaseID: int):
        """
        Get a purchase by ID.
        """
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

            purchase_dict = dict(purchase)
            purchase_dict["supplier"] = {
                "id": purchase_dict["supplier_id"],
                "name": purchase_dict["supplier_name"],
                "address": purchase_dict["supplier_address"],
                "city": purchase_dict["supplier_city"],
                "province": purchase_dict["supplier_province"],
                "prefix": purchase_dict["supplier_prefix"],
            }
            # Remove individual supplier fields
            for field in ["supplier_id", "supplier_name", "supplier_address", "supplier_city", "supplier_province", "supplier_prefix"]:
                purchase_dict.pop(field, None)

            return purchase_dict
        except Exception as e:
            log_error(f"Error fetching purchase by ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_project(projectName: str):
        """
        Get purchases by project name.
        """
        try:
            if not projectName:
                return {"error": "Project name is required", "status": 400}
            
            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
            ]
            
            conditions = [
                purchases_table.c.projectName == projectName,
                purchases_table.c.isDelete == False
            ]

            query = (
                select(*purchases_table.c, *supplier_columns)
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .where(*conditions)
                .order_by(purchases_table.c.date.desc())
            )
            purchases = await database.fetch_all(query)

            if not purchases:
                return {"error": "No purchases found for this project", "status": 404}

            # Convert the result to a list of dictionaries
            purchase_list = []
            for purchase in purchases:
                purchase_dict = dict(purchase)
                purchase_dict["supplier"] = {
                    "id": purchase_dict["supplier_id"],
                    "name": purchase_dict["supplier_name"],
                    "address": purchase_dict["supplier_address"],
                    "city": purchase_dict["supplier_city"],
                    "province": purchase_dict["supplier_province"],
                    "prefix": purchase_dict["supplier_prefix"],
                }
                # Remove individual supplier fields
                for field in ["supplier_id", "supplier_name", "supplier_address", "supplier_city", "supplier_province", "supplier_prefix"]:
                    purchase_dict.pop(field, None)
                purchase_list.append(purchase_dict)

            return purchase_list
        except Exception as e:
            log_error(f"Error fetching purchase report by project: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_ppn_report(month: int, year: int):
        """
        Get PPN report for a specific month and year.
        """
        try:
            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
                suppliers_table.c.npwp.label("supplier_npwp")
            ]
            
            conditions = [
                purchases_table.c.isDelete == False,
                purchases_table.c.ppn > 0,
                func.extract('month', purchases_table.c.date) == month,
                func.extract('year', purchases_table.c.date) == year
            ]

            query = (
                select(*purchases_table.c, *supplier_columns)
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .where(*conditions)
                .order_by(purchases_table.c.date.asc())
            )
            purchases = await database.fetch_all(query)

            if not purchases:
                return {"error": "No PPN purchases found for this period", "status": 404}

            # Convert the result to a list of dictionaries
            purchase_list = []
            for purchase in purchases:
                purchase_dict = dict(purchase)
                purchase_dict["supplier"] = {
                    "id": purchase_dict["supplier_id"],
                    "name": purchase_dict["supplier_name"],
                    "address": purchase_dict["supplier_address"],
                    "city": purchase_dict["supplier_city"],
                    "province": purchase_dict["supplier_province"],
                    "prefix": purchase_dict["supplier_prefix"],
                    "npwp": purchase_dict["supplier_npwp"],
                }
                # Remove individual supplier fields
                for field in ["supplier_id", "supplier_name", "supplier_address", "supplier_city", "supplier_province", "supplier_prefix", "supplier_npwp"]:
                    purchase_dict.pop(field, None)
                purchase_list.append(purchase_dict)

            return purchase_list
        except Exception as e:
            log_error(f"Error fetching PPN report: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_frequent_payment_by_supplier_id(supplierID: int):
        # Fetch the most frequent payment number of a supplier
        try:
            query = (
                select(
                    purchases_table.c.bankAccountNumber,
                    purchases_table.c.bankAccountName,
                    purchases_table.c.bankName,
                    func.count(purchases_table.c.bankAccountNumber).label('usage_count')
                )
                .where(purchases_table.c.supplierID == supplierID)
                .group_by(
                    purchases_table.c.bankAccountNumber,
                    purchases_table.c.bankAccountName,
                    purchases_table.c.bankName
                )
                .order_by(func.count(purchases_table.c.bankAccountNumber).desc())
                .limit(1)
            )
            result = await database.fetch_one(query)
            if not result:
                return {"error": "Supplier frequent payment not found", "status": 404}
            return {
                "bankAccountNumber": result.bankAccountNumber,
                "bankAccountName": result.bankAccountName,
                "bankName": result.bankName
            }
        except Exception as e:
            log_error(f"Error fetching frequent payment by supplier ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update_status(purchase_id: int, status_data: dict, userID: int):
        """
        Update purchase status and details.
        """
        try:
            update_query = (
                update(purchases_table)
                .where(purchases_table.c.id == purchase_id)
                .values(
                    lastStatus="ready",
                    lastStatusDescription=None,
                    updatedAt=dt.now(),
                    updatedBy=userID,
                    invoiceName=status_data["invoiceName"],
                    receiptName=status_data["receiptName"],
                    taxInvoiceName=status_data["taxInvoiceName"],
                    date=status_data["date"],
                    dueDate=status_data["dueDate"],
                    isCopAttached=status_data["isCopAttached"],
                    isCopyPurchaseOrderAttached=status_data["isCopyPurchaseOrderAttached"],
                    isInvoiceAttached=status_data["isInvoiceAttached"],
                    isReceiptAttached=status_data["isReceiptAttached"],
                    isTaxInvoiceAttached=status_data["isTaxInvoiceAttached"]
                )
            )
            result = await database.execute(update_query)
            if result == 0:
                return {"error": "Purchase not found", "status": 404}
            
            return {"message": "Purchase status updated successfully"}
        except Exception as e:
            log_error(f"Error updating purchase status: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update_payment_status(purchaseID: int, isPaid: bool):
        """
        Update the payment status of a purchase.
        """
        try:
            query = (
                update(purchases_table)
                .where(purchases_table.c.id == purchaseID)
                .values(isPaid=isPaid)
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Purchase not found", "status": 404}
            return {"message": "Payment status updated successfully"}
        except Exception as e:
            log_error(f"Error updating payment status: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def delete(purchaseID: int, userID: int):
        """
        Soft delete a purchase.
        """
        try:
            query = (
                update(purchases_table)
                .where(purchases_table.c.id == purchaseID)
                .values(isDelete=True, deletedAt=dt.now(), deletedBy=userID)
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Purchase not found", "status": 404}
            return {"message": "Purchase deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting purchase: {str(e)}")
            return {"error": str(e), "status": 500}

class PurchaseStatusRepository:
    @staticmethod
    async def create(status_data: dict):
        """
        Create a new purchase status.
        """
        try:
            query = insert(purchase_status_table).values(status_data)
            purchase_status_id = await database.execute(query)
            return purchase_status_id
        except Exception as e:
            log_error(f"Error creating purchase status: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_purchase_id(purchaseID: int):
        """
        Get all statuses for a purchase.
        """
        try:
            query = (
                select(purchase_status_table)
                .where(purchase_status_table.c.purchaseID == purchaseID)
                .order_by(purchase_status_table.c.createdAt.desc())
            )
            statuses = await database.fetch_all(query)
            return [dict(status) for status in statuses]
        except Exception as e:
            log_error(f"Error fetching purchase statuses: {str(e)}")
            return {"error": str(e), "status": 500}