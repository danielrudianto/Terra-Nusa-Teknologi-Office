from sqlalchemy import select, insert, update, delete, func, or_, and_
from utils.database import database
from models.reimbursement_model import reimbursements_table, reimbursement_items_table
from utils.logger_utils import log_error, log_info
from datetime import datetime

class ReimbursementRepository:
    
    @staticmethod
    async def count_by_project_name(projectName: str):
        try:
            query = select(func.count()).where(
                reimbursements_table.c.projectName == projectName,
            )
            count = await database.fetch_val(query)
            return count if count is not None else 0
        except Exception as e:
            log_error(f"Error counting reimbursements by project name: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def create_reimbursement(reimbursement_data: dict):
        try:
            query = insert(reimbursements_table).values(**reimbursement_data)
            reimbursement_id = await database.execute(query)
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="reimbursements",
                entityID=reimbursement_id,
                action="create",
            )
            return reimbursement_id
        except Exception as e:
            log_error(f"Error creating reimbursement: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def create_reimbursement_items(reimbursement_items_data: list):
        try:
            if not reimbursement_items_data:
                from repository.audit_log_repository import AuditLogRepository

                # Baris turunan dicatat pada dokumen induknya: riwayat dibaca
                # per dokumen, sehingga catatan terpisah tidak akan terlihat.
                await AuditLogRepository.record(
                    entity="reimbursements",
                    entityID=reimbursement_items_data[0]["reimbursementID"],
                    action="create_items",
                )

                return {"message": "No reimbursement items to create."}
            
            query = insert(reimbursement_items_table).values(reimbursement_items_data)
            await database.execute(query)
            return {"message": "Reimbursement items created successfully"}
        except Exception as e:
            log_error(f"Error creating reimbursement items: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_reimbursements(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None):
        try:
            amount_subq = (
                select(
                    reimbursement_items_table.c.reimbursementID,
                    func.sum(reimbursement_items_table.c.amount).label("amount")
                )
                .group_by(reimbursement_items_table.c.reimbursementID)
            ).subquery()

            conditions = []
            or_conditions = []
            
            if keyword and keyword != "":
                or_conditions.append(reimbursements_table.c.name.ilike(f"%{keyword}%"))
                or_conditions.append(reimbursements_table.c.projectName.ilike(f"%{keyword}%"))
                or_conditions.append(reimbursements_table.c.purchaseType.ilike(f"%{keyword}%"))
                or_conditions.append(reimbursements_table.c.bankName.ilike(f"%{keyword}%"))
                or_conditions.append(reimbursements_table.c.bankAccountName.ilike(f"%{keyword}%"))
                or_conditions.append(reimbursements_table.c.bankAccountNumber.ilike(f"%{keyword}%"))

            if or_conditions:
                conditions.append(or_(*or_conditions))

            status_conditions = []
            if filterObject.get("isPending"):
                status_conditions.append(and_(reimbursements_table.c.isApprove == False, reimbursements_table.c.isDelete == False))
            if filterObject.get("isApprove"):
                status_conditions.append(and_(reimbursements_table.c.isApprove == True, reimbursements_table.c.isDelete == False))
            if filterObject.get("isDelete"):
                status_conditions.append(and_(reimbursements_table.c.isDelete == True, reimbursements_table.c.isApprove == False))
                
            if status_conditions:
                conditions.append(or_(*status_conditions))

            payment_conditions = []
            if filterObject.get("isPaid"):
                payment_conditions.append(reimbursements_table.c.isPaid == True)
            if filterObject.get("isUnpaid"):
                payment_conditions.append(reimbursements_table.c.isPaid == False)

            if payment_conditions:
                conditions.append(or_(*payment_conditions))

            # Order by logic
            order_by_mapping = {
                "date": reimbursements_table.c.date,
                "name": reimbursements_table.c.name,
                "dueDate": reimbursements_table.c.dueDate,
                "amount": amount_subq.c.amount,
                "projectName": reimbursements_table.c.projectName
            }
            
            order_column = order_by_mapping.get(sortBy, reimbursements_table.c.date)
            order_by = order_column.desc() if sortByDirection == "desc" else order_column.asc()

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
                .where(*conditions)
                .order_by(order_by)
                .limit(pageSize)
                .offset((page - 1) * pageSize)
            )

            reimbursements = await database.fetch_all(query)

            count_query = select(func.count()).select_from(reimbursements_table).where(*conditions)
            count = await database.fetch_val(count_query)

            return {"data": reimbursements, "count": count}
        except Exception as e:
            log_error(f"Error getting reimbursements: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_reimbursement_by_id(reimbursementID: int):
        try:
            query = select(reimbursements_table).where(
                reimbursements_table.c.id == reimbursementID,
            )
            reimbursement = await database.fetch_one(query)
            if reimbursement is None:
                return {"error": "Reimbursement not found", "status": 404}
            return reimbursement
        except Exception as e:
            log_error(f"Error getting reimbursement by ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_reimbursement_items_by_reimbursement_id(reimbursementID: int):
        try:
            query = select(reimbursement_items_table).where(
                reimbursement_items_table.c.reimbursementID == reimbursementID
            )
            reimbursement_items = await database.fetch_all(query)
            return reimbursement_items
        except Exception as e:
            log_error(f"Error getting reimbursement items by ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_project(projectName: str):
        try:
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
                .where(reimbursements_table.c.isDelete == False, reimbursements_table.c.projectName == projectName)
            )

            reimbursements = await database.fetch_all(query)
            return [dict(record) for record in reimbursements]
        except Exception as e:
            log_error(f"Error getting reimbursement items by project: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def approve_reimbursement_by_id(reimbursementID: int, userID: int):
        try:
            query = (
                reimbursements_table.update()
                .where(
                    reimbursements_table.c.id == reimbursementID,
                    reimbursements_table.c.isDelete == False
                )
                .values(
                    isApprove=True,
                    approvedBy=userID,
                    approvedAt=datetime.now(),
                    updatedAt=datetime.now(),
                    updatedBy=userID
                )
            )
            await database.execute(query)
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="reimbursements",
                entityID=reimbursementID,
                action="approve",
                userID=userID,
            )
            
            return {"message": "Reimbursement approved successfully"}
        except Exception as e:
            log_error(f"Error approving reimbursement by ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def reject_reimbursement_by_id(reimbursementID: int, userID: int):
        try:
            query = (
                reimbursements_table.update()
                .where(
                    reimbursements_table.c.id == reimbursementID,
                    reimbursements_table.c.isDelete == False
                )
                .values(
                    isDelete=True,
                    deletedBy=userID,
                    deletedAt=datetime.now(),
                )
            )
            await database.execute(query)
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="reimbursements",
                entityID=reimbursementID,
                action="reject",
                userID=userID,
            )

            return {"message": "Reimbursement rejected successfully"}
        except Exception as e:
            log_error(f"Error rejecting reimbursement by ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update_payment_status(reimbursementID: int, isPaid: bool, userID: int):
        try:
            # Keadaan sebelum & sesudah dibandingkan agar nilai lama ikut
            # terekam; tanpa ini audit hanya tahu "diubah", bukan "dari apa".
            _sebelum = await database.fetch_one(
                select(reimbursements_table).where(reimbursements_table.c.id == reimbursementID)
            )
            query = (
                reimbursements_table.update()
                .where(
                    reimbursements_table.c.id == reimbursementID,
                )
                .values(
                    isPaid=isPaid,
                    updatedAt=datetime.now(),
                    updatedBy=userID
                )
            )
            await database.execute(query)
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="reimbursements",
                entityID=reimbursementID,
                action="update_payment_status",
                userID=userID,
                changes=AuditLogRepository.diff(
                    dict(_sebelum) if _sebelum else {},
                    dict(
                        await database.fetch_one(
                            select(reimbursements_table).where(
                                reimbursements_table.c.id == reimbursementID
                            )
                        )
                        or {}
                    ),
                ),
            )

            return {"message": f"Reimbursement payment status updated successfully"}
        except Exception as e:
            log_error(f"Error updating reimbursement payment status: {str(e)}")
            return {"error": str(e), "status": 500}