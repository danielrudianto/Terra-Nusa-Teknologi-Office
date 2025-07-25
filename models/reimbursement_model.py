from pydantic import BaseModel, Field
from typing import Optional, Annotated
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, select, insert, func, ForeignKey, or_, and_
from utils.database import metadata
from datetime import date as d, datetime as dt
from utils.logger_utils import log_error
from utils.database import database

class ReimbursementItems(BaseModel):
    description: str  # Description of the reimbursement item
    amount : Annotated[float, Field(ge=0)]  # Amount of the reimbursement item (greater than or equal to 0)
    date: d # Date of the reimbursement item

    @staticmethod
    async def create_reimbursement_items(reimbursement_item_data: list):
        """
        Create reimbursement items in the database.
        """
        try:
            if not reimbursement_item_data:
                return {"message": "No reimbursement items to create."}
            
            query = insert(reimbursement_items_table).values(reimbursement_item_data)
            await database.execute(query)
            return {"message": "Reimbursement items created successfully"}
        except Exception as e:
            log_error(f"Error creating reimbursement items: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_reimbursement_items_by_reimbursement_id(reimbursementID: int):
        """
        Get reimbursement items by reimbursement ID.
        """
        try:
            query = select(reimbursement_items_table).where(
                reimbursement_items_table.c.reimbursementID == reimbursementID
            )
            reimbursement_items = await database.fetch_all(query)
            return reimbursement_items
        except Exception as e:
            log_error(f"Error getting reimbursement items by ID: {str(e)}")
            return {"error": str(e), "status": 500}


reimbursement_items_table = Table(
    "reimbursement_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("reimbursementID", Integer, nullable=False),
    Column("description", String(100), nullable=False),
    Column("amount", Float(), nullable=False),
    Column("date", Date(), nullable=False),
)

# Define the Purchase model
class Reimbursement(BaseModel):
    name: str | None = None# Name of the reimbursement
    date: d  # Date of the reimbursement
    dueDate: d # Due date of the reimbursement
    projectName: str  # Name of the project
    purchaseType: str  # Type of the purchase
    bankName: str  # Name of the bank
    bankAccountName: str  # Name of the bank account
    bankAccountNumber: str  # Bank account number
    paymentMethod: str  # Payment method
    isPaid: bool = False  # Flag to indicate if the purchase is paid
    isDelete: bool = False  # Flag to indicate if the purchase is deleted
    isApprove: bool = False  # Flag to indicate if the reimbursement is approved
    approvedBy: Optional[int] = None  # ID of the user who approved the reimbursement
    approvedAt: Optional[dt] = None  # Date and time when the reimbursement was approved
    createdAt: dt = Field(default_factory=dt.now)  # Creation date
    createdBy: int | None = None  # ID of the user who created the purchase
    updatedAt: Optional[dt] = None  # Update date
    updatedBy: Optional[int] = None  # ID of the user who updated the purchase
    deletedAt: Optional[dt] = None  # Deletion date
    deletedBy: Optional[int] = None  # ID of the user who deleted the purchase
    reimbursementItems: Optional[list[ReimbursementItems]] = None  # List of reimbursement items

    @staticmethod
    async def get_reimbursements_by_project(projectName: str):
        """
        Get all reimbursements by project name.
        """
        try:
            amount_subq = (
                select(
                    reimbursement_items_table.c.reimbursementID,
                    func.sum(reimbursement_items_table.c.amount).label("amount")
                )
                .group_by(reimbursement_items_table.c.reimbursementID)
            ).subquery()

            conditions = [
                reimbursements_table.c.projectName == projectName,
                reimbursements_table.c.isDelete == False
            ]
            
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
                .order_by(reimbursements_table.c.date.asc())
                .where(*conditions)
            )

            reimbursements = await database.fetch_all(query)
            return reimbursements
        except Exception as e:
            log_error(f"Error getting reimbursements by project: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def count_by_project_name(projectName: str):
        """
        Count the number of reimbursements by project name.
        """
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
            return reimbursement_id
        except Exception as e:
            log_error(f"Error on creating reimbursement : {str(e)}")
            return {"status": 500, "error": str(e)}

    @staticmethod
    async def get_reimbursements(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None):
        """
        Get all reimbursements with pagination and sorting.
        """
        try:
            # "SELECT reimbursements.*, a.amount FROM reimbursements LEFT JOIN (SELECT reimbursementID, SUM(amount) as amount FROM reimbursement_items GROUP BY reimbursementID) a ON reimbursements.id = a.reimbursementID ORDER BY date DESC LIMIT 10 OFFSET (page - 1) * 10"
            amount_subq = (
                select(
                    reimbursement_items_table.c.reimbursementID,
                    func.sum(reimbursement_items_table.c.amount).label("amount")
                )
                .group_by(reimbursement_items_table.c.reimbursementID)
            ).subquery()

            conditions = []
            or_conditions = []
            if(keyword is not None and keyword != ""):
                or_conditions.append(reimbursements_table.c.name.ilike(f"%{keyword}%"))
                or_conditions.append(reimbursements_table.c.projectName.ilike(f"%{keyword}%"))
                or_conditions.append(reimbursements_table.c.purchaseType.ilike(f"%{keyword}%"))
                or_conditions.append(reimbursements_table.c.bankName.ilike(f"%{keyword}%"))
                or_conditions.append(reimbursements_table.c.bankAccountName.ilike(f"%{keyword}%"))
                or_conditions.append(reimbursements_table.c.bankAccountNumber.ilike(f"%{keyword}%"))

            conditions.append(or_(*or_conditions))

            or_conditions = []
            if filterObject.get("isPending"):
                or_conditions.append(reimbursements_table.c.isApprove == False and reimbursements_table.c.isDelete == False)
            if filterObject.get("isApprove"):
                or_conditions.append(reimbursements_table.c.isApprove == True and reimbursements_table.c.isDelete == False)
            if filterObject.get("isDelete"):
                and_conditions = []
                and_conditions.append(reimbursements_table.c.isDelete == True)
                and_conditions.append(reimbursements_table.c.isApprove == False)
                or_conditions.append(and_(*and_conditions))
                
            conditions.append(or_(*or_conditions))

            or_conditions = []
            if filterObject.get("isPaid"):
                or_conditions.append(reimbursements_table.c.isPaid == True)
            if filterObject.get("isUnpaid"):
                or_conditions.append(reimbursements_table.c.isPaid == False)

            conditions.append(or_(*or_conditions))

            if sortBy == "date":
                order_by = reimbursements_table.c.date.desc() if sortByDirection == "desc" else reimbursements_table.c.date.asc()
            elif sortBy == "name":
                order_by = reimbursements_table.c.name.desc() if sortByDirection == "desc" else reimbursements_table.c.name.asc()
            elif sortBy == "dueDate":
                order_by = reimbursements_table.c.dueDate.desc() if sortByDirection == "desc" else reimbursements_table.c.dueDate.asc()
            elif sortBy == "amount":
                order_by = (amount_subq.c.amount).desc() if sortByDirection == "desc" else (amount_subq.c.amount).asc()
            elif sortBy == "projectName":
                order_by = reimbursements_table.c.projectName.desc() if sortByDirection == "desc" else reimbursements_table.c.projectName.asc()
            else:
                order_by = reimbursements_table.c.date.desc()

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

            #Count the total number of purchases
            count_query = select(func.count()).select_from(reimbursements_table).where(*conditions)
            count = await database.fetch_val(count_query)

            return {"data": reimbursements, "count": count}
        except Exception as e:
            log_error(f"Error getting reimbursements: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_reimbursement_by_id(reimbursementID: int):
        """
        Get a reimbursement by ID.
        """
        try:
            query = select(reimbursements_table).where(
                reimbursements_table.c.id == reimbursementID,
                reimbursements_table.c.isDelete == False
            )
            reimbursement = await database.fetch_one(query)
            if reimbursement is None:
                return {"error": "Reimbursement not found", "status": 404}
            return reimbursement
        except Exception as e:
            log_error(f"Error getting reimbursement by ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def approve_reimbursement_by_id(reimbursementID: int, userID: int):
        """
        Approve a reimbursement by ID.
        """
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
                    approvedAt=dt.now(),
                    updatedAt=dt.now(),
                    updatedBy=userID
                )
            )
            await database.execute(query)
            return {"message": "Reimbursement approved successfully"}
        except Exception as e:
            log_error(f"Error approving reimbursement by ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def reject_reimbursement_by_id(reimbursementID: int, userID: int):
        """
        Reject a reimbursement by ID.
        """
        try:
            query = (
                reimbursements_table.update()
                .where(
                    reimbursements_table.c.id == reimbursementID,
                    reimbursements_table.c.isDelete == False
                )
                .values(
                    isDelete=True,
                    approvedBy=userID,
                    approvedAt=dt.now(),
                )
            )
            await database.execute(query)
            return {"message": "Reimbursement rejected successfully"}
        except Exception as e:
            log_error(f"Error rejecting reimbursement by ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update_payment_status(reimbursementID: int, isPaid: bool, userID: int):
        """
        Update the payment status of a reimbursement.
        """
        try:
            query = (
                reimbursements_table.update()
                .where(
                    reimbursements_table.c.id == reimbursementID,
                )
                .values(
                    isPaid=isPaid,
                )
            )
            await database.execute(query)
            return {"message": f"Reimbursement updated successfully"}
        except Exception as e:
            log_error(f"Error updating reimbursement payment status: {str(e)}")
            return {"error": str(e), "status": 500}

# Define the SQLAlchemy table
reimbursements_table = Table(
    "reimbursements",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(100), nullable=False),
    Column("date", Date(), nullable=False),
    Column("dueDate", Date(), nullable=True),
    Column("projectName", String(100), nullable=False),
    Column("purchaseType", String(100), nullable=False),
    Column("bankName", String(100), nullable=False),
    Column("bankAccountName", String(100), nullable=False),
    Column("bankAccountNumber", String(100), nullable=False),
    Column("paymentMethod", String(100), nullable=False),
    Column("isPaid", Boolean(), nullable=False, default=False),
    Column("isDelete", Boolean(), nullable=False, default=False),
    Column("isApprove", Boolean(), nullable=False, default=False),
    Column("approvedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("approvedAt", DateTime(), nullable=True, default=None),
    Column("createdAt", DateTime(), nullable=False, default=dt.now()),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
)

