from pydantic import BaseModel
from datetime import datetime as dt, date as d
from sqlalchemy import Table, Column, Integer, ForeignKey, Float, Date, String, select, func, Boolean, DateTime
from utils.database import metadata, database
from utils.logger_utils import log_error
from models.client_model import clients_table  # Assuming client_ is defined in client_model

class SalesInvoice(BaseModel):
    name: str  # Name of the sales invoice
    date: d  # Date of the sales invoice in ISO format
    projectName: str  # Name of the project
    clientID: int  # ID of the client
    dpp: float  # DPP (Dasar Pengenaan Pajak) amount
    pphCode: str | None
    pphTaxObject: str | None
    pphPercentage: float
    ppn: float
    spkNumber: str
    description: str
    bankAccountID: int
    createdBy: int | None = None # ID of the user who created the invoice, default to 1
    createdAt: dt = dt.now()
    isApprove: bool = False  # Whether the invoice is confirmed or not
    isDelete: bool = False  # Whether the invoice is deleted or not
    updatedBy: int | None = None  # ID of the user who confirmed the invoice, default to None
    updatedAt: dt | None = None  # Date and time when the invoice was confirmed, default to None

    @staticmethod
    async def create_sales_invoice(sales_invoice_data: dict):
        """
        Create a sales invoice in the database.
        """
        try:
            # Here you would typically insert the sales invoice into the database
            # For demonstration purposes, we return a success message
            query = sales_invoice_tables.insert().values(
                **sales_invoice_data,
            )
            result = await database.execute(query)
            if not result:
                return {"error": "Failed to create sales invoice", "status": 500}
            
            return {"message": "Sales invoice created successfully", "salesInvoiceID": result}
        except Exception as e:
            return {"error": str(e), "status": 500}
    
    @staticmethod
    async def get_sales_invoice_by_name(name: str):
        """
        Get a sales invoice by its name.
        """
        try:
            query = select(sales_invoice_tables).where(sales_invoice_tables.c.name == name)
            result = await database.fetch_one(query)
            return result
        except Exception as e:
            log_error(f"Error fetching sales invoice by name: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_sales_invoice_by_id(id: int):
        """
        Fetch sales invoice by ID
        """
        try:
            client_column = [
                clients_table.c.name.label("client_name"),
                clients_table.c.id.label("client_id"),
                clients_table.c.address.label("client_address"),
                clients_table.c.city.label("client_city"),
                clients_table.c.province.label("client_province"),
                clients_table.c.prefix.label("client_prefix"),
            ]
            query = select(
                *sales_invoice_tables.c,
                *client_column
            ).join(clients_table, sales_invoice_tables.c.clientID == clients_table.c.id
            ).where(sales_invoice_tables.c.id == id)
            result = await database.fetch_one(query)
            return result
        except Exception as e:
            log_error(f"Error fetching sales invoices: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def reject_sales_invoice_by_id(id: int, userID: int):
        try:
            query = (
                sales_invoice_tables.update()
                .where(sales_invoice_tables.c.id == id)
                .values(isDelete=True, updatedAt=dt.now(), updatedBy=userID)
            )
            await database.execute(query)
            return {"message": "Sales invoice deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting sales invoice: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def approve_sales_invoice_id(id: int, taxInvoiceName: str | None, userID: int):
        try:
            query = (
                sales_invoice_tables.update()
                .where(sales_invoice_tables.c.id == id)
                .values(
                    isApprove=True, 
                    updatedAt=dt.now(), 
                    updatedBy=userID, 
                    taxInvoiceName=taxInvoiceName
                )
            )
            await database.execute(query)
            return {"message": "Sales invoice approved successfully"}
        except Exception as e:
            log_error(f"Error deleting sales invoice: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def check_sales_invoice(description: str, projectName: str, clientID: int):
        """
        Check if a sales invoice with the same description, project name, and client ID already exists.
        """
        try:
            query = select(sales_invoice_tables.c.id).where(
                sales_invoice_tables.c.description == description,
                sales_invoice_tables.c.projectName == projectName,
                sales_invoice_tables.c.clientID == clientID
            )
            result = await database.fetch_one(query)
            return result is not None
        except Exception as e:
            log_error(f"Error checking sales invoice: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_sales_invoices(page: int, pageSize: int):
        """
        Get sales invoices with pagination.
        """
        try:
            client_column = [
                clients_table.c.name.label("client_name"),
                clients_table.c.id.label("client_id"),
                clients_table.c.address.label("client_address"),
                clients_table.c.city.label("client_city"),
                clients_table.c.province.label("client_province"),
                clients_table.c.prefix.label("client_prefix"),
            ]
            offset = (page - 1) * pageSize
            query = select(
                    *sales_invoice_tables.c,
                    *client_column
                ).join(clients_table, sales_invoice_tables.c.clientID == clients_table.c.id
                ).order_by(
                    sales_invoice_tables.c.date.desc()
                ).offset(offset).limit(pageSize)

            result = await database.fetch_all(query)

            #Now the count
            count_query = (
                    select(func.count())
                .select_from(sales_invoice_tables)
            )
            count = await database.fetch_val(count_query)
            total_count = await database.fetch_val(count_query)
            
            return {"data": result, "count": total_count}
        except Exception as e:
            log_error(f"Error fetching sales invoices: {str(e)}")
            return {"error": str(e), "status": 500}
        
sales_invoice_tables = Table(
    "sales_invoices",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False),
    Column("date", Date, nullable=False),
    Column("projectName", String(10), nullable=False),
    Column("clientID", Integer, ForeignKey("clients.id"), nullable=False),
    Column("dpp", Float, nullable=False, default=0.0),
    Column("pphCode", String(100), nullable=True),
    Column("pphTaxObject", String(500), nullable=True),
    Column("pphPercentage", Float, nullable=False, default=0.0),
    Column("ppn", Float, nullable=False, default=0.0),
    Column("spkNumber", String(100), nullable=False),
    Column("taxInvoiceName", String(100), nullable=True, default=None),
    Column("description", String(100), nullable=True),
    Column("bankAccountID", Integer, ForeignKey("bank_accounts.id"), nullable=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False, default=1),
    Column("createdAt", Date, nullable=False, default=dt.utcnow().date()),
    Column("isApprove", Boolean, nullable=False, default=False),
    Column("isDelete", Boolean, nullable=False, default=False),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("updatedAt", DateTime, nullable=True, default=None)
)