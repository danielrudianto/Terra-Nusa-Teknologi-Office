from sqlalchemy import select, func, or_, insert, update
from utils.database import database
from utils.logger_utils import log_error
from models.purchase_model import purchases_table, purchase_status_table
from models.purchase_order_model import purchase_orders_table
from models.supplier_model import suppliers_table
from models.payment_outgoing_model import payments_outgoing_table
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
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="purchases",
                entityID=purchase_id,
                action="create",
            )
            return purchase_id
        except Exception as e:
            log_error(f"Error creating purchase: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

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

            # Tabel purchases hanya menyimpan NAMA purchase order, bukan
            # id-nya. Id diambil lewat sambungan nama agar dokumennya dapat
            # dibuka langsung dari daftar pembelian — tanpa ini, pengguna
            # harus menyalin nomornya lalu mencarinya di halaman lain.
            query = (
                select(
                    *purchases_table.c,
                    *supplier_columns,
                    purchase_orders_table.c.id.label("purchase_order_id"),
                )
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .join(
                    purchase_orders_table,
                    purchases_table.c.purchaseOrderName
                    == purchase_orders_table.c.name,
                    isouter=True,
                )
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
            return {"error": "Internal server error.", "status": 500}

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
            return {"error": "Internal server error.", "status": 500}

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
            # Nama pembuat ikut diambil agar tampilan detail bisa
            # menampilkannya tanpa permintaan tambahan.
            #
            # Impor ditaruh di dalam fungsi: menaruhnya di kepala berkas
            # menambah ketergantungan saat modul dimuat, dan pada sebagian
            # susunan proyek itu memicu impor melingkar sehingga
            # PurchaseRepository gagal terbaca.
            from models.user_model import users_table

            query = (
                select(
                    *purchases_table.c,
                    *supplier_columns,
                    users_table.c.name.label("createdByName"),
                    # Id purchase order disambungkan lewat namanya, sama
                    # seperti pada daftar: tabel purchases hanya menyimpan
                    # nomornya sebagai teks.
                    purchase_orders_table.c.id.label("purchase_order_id"),
                )
                .select_from(
                    purchases_table.join(
                        suppliers_table,
                        purchases_table.c.supplierID == suppliers_table.c.id,
                    ).outerjoin(
                        users_table,
                        purchases_table.c.createdBy == users_table.c.id,
                    ).outerjoin(
                        purchase_orders_table,
                        purchases_table.c.purchaseOrderName
                        == purchase_orders_table.c.name,
                    )
                )
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
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_purchases_by_purchase_order_name(purchase_order_name: str):
        """
        Get purchases by purchase order name.
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

            conditions = [
                purchases_table.c.isDelete == False,
                purchases_table.c.purchaseOrderName == purchase_order_name
            ]

            query = (
                select(*purchases_table.c, *supplier_columns)
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .where(*conditions)
            )

            purchases = await database.fetch_all(query)

            return {"data": purchases}
        except Exception as e:
            log_error(f"Error fetching purchases: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

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
            return {"error": "Internal server error.", "status": 500}

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
                purchases_table.c.isInternal == False,
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
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_monthly_recap(month: int, year: int):
        try:
            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
                suppliers_table.c.npwp.label("supplier_npwp"),
            ]

            query = (
                select(*purchases_table.c, *supplier_columns)
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .where(
                    func.extract('month', purchases_table.c.date) == month,
                    func.extract('year', purchases_table.c.date) == year,
                    purchases_table.c.isDelete == False
                )
                .order_by(purchases_table.c.date.asc())
            )

            results = await database.fetch_all(query)
            return results
        except Exception as e:
            log_error(f"Error fetching monthly purchase report: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
        
    @staticmethod
    async def get_monthly_ap(month: int, year: int):
        """
            The goal is to determine the purchase invoice on this month and year, and before that (example, the month and year is 1 and 2026, then search sales invoices that is less than "2026-31-01")
            Then left join with the payment received
            if the difference is less than 5 Rupiah, then consider it as paid
            The others that has difference more than 5 Rupiah should be considered as AR
        """
        try:
            
            # Hitung batas akhir bulan
            if month == 12:
                end_date = dt(year + 1, 1, 1)
            else:
                end_date = dt(year, month + 1, 1)


            # Subquery total payment per purchase
            payment_subquery = (
                select(
                    payments_outgoing_table.c.purchaseID.label("purchase_id"),
                    func.coalesce(func.sum(payments_outgoing_table.c.amount), 0).label("total_paid")
                )
                .where(
                    payments_outgoing_table.c.date < end_date,
                    payments_outgoing_table.c.isDelete == False,
                    payments_outgoing_table.c.isApprove == True,
                )
                .group_by(payments_outgoing_table.c.purchaseID)
                .subquery()
            )

            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
                suppliers_table.c.npwp.label("supplier_npwp"),
            ]

            # Main query
            query = (
                select(
                    purchases_table.c.id,
                    purchases_table.c.invoiceName,
                    purchases_table.c.receiptName,
                    purchases_table.c.taxInvoiceName,
                    purchases_table.c.purchaseOrderName,
                    purchases_table.c.projectName,
                    purchases_table.c.date,
                    purchases_table.c.dpp,
                    purchases_table.c.pbbkb,
                    purchases_table.c.pphPercentage,
                    purchases_table.c.pphCode,
                    purchases_table.c.ppn,
                    purchases_table.c.pphTaxObject,
                    purchases_table.c.otherValue,
                    purchases_table.c.otherValueNote,
                    func.coalesce(payment_subquery.c.total_paid, 0).label("total_paid"),
                    (
                        (purchases_table.c.ppn * purchases_table.c.dpp / 100 + 
                         purchases_table.c.dpp + purchases_table.c.pbbkb + 
                         purchases_table.c.otherValue - 
                         purchases_table.c.pphPercentage * purchases_table.c.dpp / 100) -
                        func.coalesce(payment_subquery.c.total_paid, 0)
                    ).label("remaining"),
                    *supplier_columns
                )
                .outerjoin(
                    payment_subquery,
                    purchases_table.c.id == payment_subquery.c.purchase_id
                )
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .where(
                    purchases_table.c.date < end_date,
                    purchases_table.c.isDelete == False,
                    purchases_table.c.isInternal == False,
                    #Where the difference is less than 5 Rupiah
                    (purchases_table.c.ppn * purchases_table.c.dpp / 100 + 
                     purchases_table.c.dpp + purchases_table.c.pbbkb + 
                     purchases_table.c.otherValue - 
                     purchases_table.c.pphPercentage * purchases_table.c.dpp / 100) -
                    func.coalesce(payment_subquery.c.total_paid, 0) >= 5
                )
            )

            results = await database.fetch_all(query)

            ap_list = []

            for row in results:
                data = dict(row)
                if data["remaining"] is not None and data["remaining"] > 5:
                    ap_list.append(data)

            return {
                "data": ap_list,
                "count": len(ap_list)
            }

        except Exception as e:
            log_error(f"Error fetching AP report: {str(e)}")
            raise

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
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update_status(purchase_id: int, status_data: dict, userID: int):
        """
        Update purchase status and details.
        """
        try:
            # Keadaan sebelum & sesudah dibandingkan agar nilai lama ikut
            # terekam; tanpa ini audit hanya tahu "diubah", bukan "dari apa".
            _sebelum = await database.fetch_one(
                select(purchases_table).where(purchases_table.c.id == purchase_id)
            )
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
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="purchases",
                entityID=purchase_id,
                action="update_status",
                userID=userID,
                changes=AuditLogRepository.diff(
                    dict(_sebelum) if _sebelum else {},
                    dict(
                        await database.fetch_one(
                            select(purchases_table).where(
                                purchases_table.c.id == purchase_id
                            )
                        )
                        or {}
                    ),
                ),
            )
            
            return {"message": "Purchase status updated successfully"}
        except Exception as e:
            log_error(f"Error updating purchase status: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update_payment_status(purchaseID: int, isPaid: bool):
        """
        Update the payment status of a purchase.
        """
        try:
            # Keadaan sebelum & sesudah dibandingkan agar nilai lama ikut
            # terekam; tanpa ini audit hanya tahu "diubah", bukan "dari apa".
            _sebelum = await database.fetch_one(
                select(purchases_table).where(purchases_table.c.id == purchaseID)
            )
            query = (
                update(purchases_table)
                .where(purchases_table.c.id == purchaseID)
                .values(isPaid=isPaid)
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Purchase not found", "status": 404}
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="purchases",
                entityID=purchaseID,
                action="update_payment_status",
                changes=AuditLogRepository.diff(
                    dict(_sebelum) if _sebelum else {},
                    dict(
                        await database.fetch_one(
                            select(purchases_table).where(
                                purchases_table.c.id == purchaseID
                            )
                        )
                        or {}
                    ),
                ),
            )

            return {"message": "Payment status updated successfully"}
        except Exception as e:
            log_error(f"Error updating payment status: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

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
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="purchases",
                entityID=purchaseID,
                action="delete",
                userID=userID,
            )

            return {"message": "Purchase deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting purchase: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

class PurchaseStatusRepository:
    @staticmethod
    async def create(status_data: dict):
        """
        Create a new purchase status.
        """
        try:
            query = insert(purchase_status_table).values(status_data)
            purchase_status_id = await database.execute(query)
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="purchases",
                entityID=purchase_status_id,
                action="create",
            )
            return purchase_status_id
        except Exception as e:
            log_error(f"Error creating purchase status: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

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
            return {"error": "Internal server error.", "status": 500}