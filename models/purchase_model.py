from pydantic import BaseModel, Field
from typing import Optional, Annotated
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey, or_, select, func, insert
from utils.database import metadata
from datetime import datetime as d
from utils.logger_utils import log_error, log_info
from models.supplier_model import suppliers_table
from utils.database import database

# Define the Purchase model
class Purchase(BaseModel):
    invoiceName: str  # Name of the invoice
    receiptName: str  # Name of the receipt
    taxInvoiceName: str | None = None  # Name of the tax invoice
    supplierID: int  # ID of the supplier
    date: d  # Date of the purchase
    dueDate: d | None = None
    purchaseOrderName: str  # Name of the purchase order
    projectName: str  # Name of the project
    purchaseType: str  # Type of the purchase
    procurementType: str # Type of procurement (either goods or other)
    dpp: Annotated[float, Field(ge=0)]  # DPP value (greater than or equal to 0)
    ppn: Annotated[float, Field(ge=0)]  # PPN value (optional)
    pbbkb: Annotated[float, Field(ge=0)]  # PBBKB value (optional)
    pphCode: str | None  # PPH code
    pphTaxObject: str | None  # PPH tax object
    pphPercentage: Annotated[float, Field(ge=0, le=16)]  # PPH percentage (0-10%)
    otherValue: Optional[float] = None  # Other value (optional)
    otherValueNote: Optional[str] = None  # Note for other value (optional)
    isInvoiceAttached: bool  # Flag to indicate if the invoice is attached
    isReceiptAttached: bool  # Flag to indicate if the receipt is attached
    isTaxInvoiceAttached: bool  # Flag to indicate if the tax invoice is attached
    isCopAttached: bool  # Flag to indicate if the COP is attached
    isCopyPurchaseOrderAttached: bool  # Flag to indicate if the copy purchase order is attached
    bankName: str  # Name of the bank
    bankAccountName: str  # Name of the bank account
    bankAccountNumber: str  # Bank account number
    paymentMethod: str  # Payment method
    isPaid: bool = False  # Flag to indicate if the purchase is paid
    isDelete: bool = False  # Flag to indicate if the purchase is deleted
    lastStatus: str  # Last status of the purchase
    lastStatusDescription: str | None

    @staticmethod
    async def get_purchases(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None):
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
        if(keyword is not None and keyword != ""):
            or_conditions.append(purchases_table.c.purchaseOrderName.ilike(f"%{keyword}%"))
            or_conditions.append(purchases_table.c.invoiceName.ilike(f"%{keyword}%"))
            or_conditions.append(purchases_table.c.receiptName.ilike(f"%{keyword}%"))
            or_conditions.append(purchases_table.c.taxInvoiceName.ilike(f"%{keyword}%"))
            or_conditions.append(suppliers_table.c.name.ilike(f"%{keyword}%"))
        conditions.append(or_(*or_conditions))

        or_conditions = []
        if filterObject.get("isDue"):
            or_conditions.append(purchases_table.c.dueDate <= d.now().date())
        if filterObject.get("isNotDue"):
            or_conditions.append(purchases_table.c.dueDate > d.now().date())

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
            order_by = purchases_table.c.invoiceName.desc() if sortByDirection == "desc" else purchases_table.c.invoiceName.asc()
        elif sortBy == "project":
            order_by = purchases_table.c.projectName.desc() if sortByDirection == "desc" else purchases_table.c.projectName.asc()
        else:
            order_by = purchases_table.c.date.desc()
            
        
        try:
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
            count_query = (
                    select(func.count())
                .select_from(purchases_table.join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id))
                .where(*conditions)
            )
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
    async def create_purchase(purchase_data: dict):
        """
        Create a new purchase in the database.
        """
        try:
            query = insert(purchases_table).values(**purchase_data)
            purchase_id = await database.execute(query)
            return purchase_id
        except Exception as e:
            log_error(f"Error creating purchase: {str(e)}")
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
    async def get_purchase_by_project(projectName: str):
        try:
            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
            ]
            # Query to get all purchases for the specified project
            if not projectName:
                return {"error": "Project name is required", "status": 400}
            
            conditions = [
                purchases_table.c.projectName == projectName,
                purchases_table.c.isDelete == False
            ]

            order_by = purchases_table.c.date.desc()
            
            query = (
                select(*purchases_table.c, *supplier_columns)
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .where(*conditions)
                .order_by(order_by)
            )
            purchases = await database.fetch_all(query)

            if not purchases:
                return {"error": "No purchases found for this project", "status": 404}

            # Convert the result to a list of dictionaries
            purchase_list = [dict(purchase) for purchase in purchases]
            return purchase_list
        except Exception as e:
            log_error(f"Error fetching purchase report by project: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update_payment_status(purchaseID: int, isPaid: bool):
        """
        Update the payment status of a purchase.
        """
        log_info(f"Updating payment status for purchase ID: {purchaseID} to {'paid' if isPaid else 'unpaid'}")
        try:
            query = (
                purchases_table.update()
                .where(purchases_table.c.id == purchaseID)
                .values(isPaid=isPaid)
            )
            await database.execute(query)
            return {"message": "Payment status updated successfully"}
        except Exception as e:
            log_error(f"Error updating payment status: {str(e)}")
            return {"error": str(e), "status": 500}

class PurchaseStatus(BaseModel):
    id: int  # ID of the purchase
    status: str  # Status of the purchase
    createdAt: d  # Creation date of the purchase
    description: str  # Description of the status

    @staticmethod
    async def create_purchase_status(status_data: dict):
        status_query = insert(purchase_status_table).values(
            purchaseID=status_data["purchaseID"],
            status=status_data["status"],
            createdAt=status_data["createdAt"],
            description=status_data["description"],
            createdBy=status_data["createdBy"],
        )
        purchase_status_id = await database.execute(status_query)
        return purchase_status_id


class PurchaseUpdateStatus(BaseModel):
    id: int  # ID of the purchase
    isInvoiceAttached: bool  # Flag to indicate if the invoice is attached
    isReceiptAttached: bool  # Flag to indicate if the receipt is attached
    isTaxInvoiceAttached: bool  # Flag to indicate if the tax invoice is attached
    isCopAttached: bool  # Flag to indicate if the COP is attached
    isCopyPurchaseOrderAttached: bool  # Flag to indicate if the copy purchase order is attached    
    invoiceName: str  # Name of the invoice
    receiptName: str  # Name of the receipt
    taxInvoiceName: str | None  # Name of the tax invoice
    date: d  # Date of the purchase
    dueDate: d  # Due date of the purchase

# Define the SQLAlchemy table
purchases_table = Table(
    "purchases",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("invoiceName", String(100), nullable=False),
    Column("receiptName", String(100), nullable=False),
    Column("taxInvoiceName", String(100), nullable=True),
    Column("supplierID", Integer, nullable=False),
    Column("date", Date(), nullable=False),
    Column("dueDate", Date(), nullable=True),
    Column("purchaseOrderName", String(100), nullable=False),
    Column("projectName", String(100), nullable=False),
    Column("purchaseType", String(100), nullable=False),
    Column("procurementType", String(100), nullable=False, default="goods"),
    Column("dpp", Float(), nullable=False),
    Column("ppn", Float(), nullable=False),
    Column("pbbkb", Float(), nullable=False),
    Column("pphCode", String(100), nullable=True),
    Column("pphTaxObject", String(500), nullable=True),
    Column("pphPercentage", Float(), nullable=False),
    Column("otherValue", Float(), nullable=True),
    Column("otherValueNote", String(255), nullable=True),
    Column("isInvoiceAttached", Boolean(), nullable=False),
    Column("isReceiptAttached", Boolean(), nullable=False),
    Column("isTaxInvoiceAttached", Boolean(), nullable=False),
    Column("isCopAttached", Boolean(), nullable=False),
    Column("isCopyPurchaseOrderAttached", Boolean(), nullable=False),
    Column("bankName", String(100), nullable=False),
    Column("bankAccountName", String(100), nullable=False),
    Column("bankAccountNumber", String(100), nullable=False),
    Column("paymentMethod", String(100), nullable=False),
    Column("isPaid", Boolean(), nullable=False, default=False),
    Column("isDelete", Boolean(), nullable=False, default=False),
    Column("createdAt", DateTime(), nullable=False, default=d.now()),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("lastStatus", String(100), nullable=False, default="Waiting"),
)

# Define the PurchaseStatus SQLAlchemy table
purchase_status_table = Table(
    "purchase_status",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("purchaseID", Integer, nullable=False),
    Column("status", String(100), nullable=False),
    Column("createdBy", Integer, nullable=False),
    Column("createdAt", DateTime(), nullable=False, default=d.now()),
    Column("description", String(255), nullable=True),
)