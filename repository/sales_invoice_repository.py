from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, or_, desc, asc
from utils.database import database
from utils.logger_utils import log_error
from datetime import datetime as dt
from models.sales_invoice_model import sales_invoice_tables
from models.client_model import clients_table
from schemas.sales_invoice_schema import SalesInvoiceCreate, SalesInvoiceUpdate, SalesInvoiceWithClientResponse

class SalesInvoiceRepository:
    @staticmethod
    async def create(sales_invoice_data: SalesInvoiceCreate) -> Dict[str, Any]:
        """
        Create a sales invoice in the database.
        """
        try:
            query = sales_invoice_tables.insert().values(
                **sales_invoice_data.model_dump(exclude_none=True),
                createdAt=dt.now()
            )
            result = await database.execute(query)
            return {"message": "Sales invoice created successfully", "sales_invoice_id": result}
        except Exception as e:
            log_error(f"Error creating sales invoice: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_project(projectName: str):
        try:
            client_columns = [
                clients_table.c.name.label("client_name"),
                clients_table.c.id.label("client_id"),
                clients_table.c.address.label("client_address"),
                clients_table.c.city.label("client_city"),
                clients_table.c.province.label("client_province"),
                clients_table.c.prefix.label("client_prefix"),
            ]
            
            query = select(
                *sales_invoice_tables.c,
                *client_columns
            ).join(
                clients_table, 
                sales_invoice_tables.c.clientID == clients_table.c.id
            ).where(
                sales_invoice_tables.c.projectName == projectName,
                sales_invoice_tables.c.isDelete == False
            )
            
            result = await database.fetch_all(query)
            return [dict(row) for row in result]
        except Exception as e:
            log_error(f"Error fetching sales invoice by name: {str(e)}")
            raise

    @staticmethod
    async def get_by_id(sales_invoice_id: int) -> Optional[SalesInvoiceWithClientResponse]:
        """
        Get a sales invoice by ID with client information.
        """
        try:
            client_columns = [
                clients_table.c.name.label("client_name"),
                clients_table.c.id.label("client_id"),
                clients_table.c.address.label("client_address"),
                clients_table.c.city.label("client_city"),
                clients_table.c.province.label("client_province"),
                clients_table.c.prefix.label("client_prefix"),
            ]
            
            query = select(
                *sales_invoice_tables.c,
                *client_columns
            ).join(
                clients_table, 
                sales_invoice_tables.c.clientID == clients_table.c.id
            ).where(
                sales_invoice_tables.c.id == sales_invoice_id
            )
            
            result = await database.fetch_one(query)
            return SalesInvoiceWithClientResponse.model_validate(dict(result)) if result else None
        except Exception as e:
            log_error(f"Error fetching sales invoice by ID: {str(e)}")
            raise

    @staticmethod
    async def get_by_name(name: str) -> Optional[SalesInvoiceWithClientResponse]:
        """
        Get a sales invoice by name.
        """
        try:
            client_columns = [
                clients_table.c.name.label("client_name"),
                clients_table.c.id.label("client_id"),
                clients_table.c.address.label("client_address"),
                clients_table.c.city.label("client_city"),
                clients_table.c.province.label("client_province"),
                clients_table.c.prefix.label("client_prefix"),
            ]
            
            query = select(
                *sales_invoice_tables.c,
                *client_columns
            ).join(
                clients_table, 
                sales_invoice_tables.c.clientID == clients_table.c.id
            ).where(
                sales_invoice_tables.c.name == name
            )
            
            result = await database.fetch_one(query)
            return SalesInvoiceWithClientResponse.model_validate(dict(result)) if result else None
        except Exception as e:
            log_error(f"Error fetching sales invoice by name: {str(e)}")
            raise

    @staticmethod
    async def get_paginated(
        page: int = 1,
        page_size: int = 10,
        sort_by: str = "date",
        sort_direction: str = "desc",
        keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get paginated sales invoices with sorting and filtering.
        """
        try:
            client_columns = [
                clients_table.c.name.label("client_name"),
                clients_table.c.id.label("client_id"),
                clients_table.c.address.label("client_address"),
                clients_table.c.city.label("client_city"),
                clients_table.c.province.label("client_province"),
                clients_table.c.prefix.label("client_prefix"),
            ]

            # Build conditions
            conditions = []
            if keyword:
                keyword_filter = f"%{keyword}%"
                search_conditions = [
                    sales_invoice_tables.c.projectName.ilike(keyword_filter),
                    sales_invoice_tables.c.name.ilike(keyword_filter),
                    clients_table.c.name.ilike(keyword_filter),
                ]
                conditions.append(or_(*search_conditions))

            # Determine order by
            if sort_by == "date":
                order_column = sales_invoice_tables.c.date
            elif sort_by == "name":
                order_column = sales_invoice_tables.c.name
            elif sort_by == "dpp":
                order_column = sales_invoice_tables.c.dpp
            elif sort_by == "client":
                order_column = clients_table.c.name
            elif sort_by == "spkNumber":
                order_column = sales_invoice_tables.c.spkNumber
            elif sort_by == "project":
                order_column = sales_invoice_tables.c.projectName
            else:
                order_column = sales_invoice_tables.c.date

            # Apply sort direction
            if sort_direction.lower() == "desc":
                order_by = desc(order_column)
            else:
                order_by = asc(order_column)

            # Build data query
            data_query = (
                select(
                    *sales_invoice_tables.c,
                    *client_columns
                )
                .join(clients_table, sales_invoice_tables.c.clientID == clients_table.c.id)
                .where(*conditions)
                .order_by(order_by)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )

            # Build count query
            count_query = (
                select(func.count())
                .select_from(sales_invoice_tables)
                .join(clients_table, sales_invoice_tables.c.clientID == clients_table.c.id)
                .where(*conditions)
            )

            # Execute queries
            sales_invoices_data = await database.fetch_all(data_query)
            total_count = await database.fetch_val(count_query)

            sales_invoices = [
                SalesInvoiceWithClientResponse.model_validate(dict(row)) 
                for row in sales_invoices_data
            ]

            return {
                "data": sales_invoices,
                "count": len(sales_invoices),
                "total_count": total_count or 0,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_count + page_size - 1) // page_size if total_count else 0
            }

        except Exception as e:
            log_error(f"Error fetching sales invoices: {str(e)}")
            raise

    @staticmethod
    async def check_duplicate(
        description: str, 
        project_name: str, 
        client_id: int
    ) -> bool:
        """
        Check if a sales invoice with the same description, project name, and client ID exists.
        """
        try:
            query = select(sales_invoice_tables.c.id).where(
                sales_invoice_tables.c.description == description,
                sales_invoice_tables.c.projectName == project_name,
                sales_invoice_tables.c.clientID == client_id
            )
            result = await database.fetch_one(query)
            return result is not None
        except Exception as e:
            log_error(f"Error checking duplicate sales invoice: {str(e)}")
            raise

    @staticmethod
    async def reject(sales_invoice_id: int, user_id: int) -> Dict[str, Any]:
        """
        Soft delete a sales invoice.
        """
        try:
            query = (
                sales_invoice_tables.update()
                .where(sales_invoice_tables.c.id == sales_invoice_id)
                .values(
                    isDelete=True,
                    updatedAt=dt.now(),
                    updatedBy=user_id
                )
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Sales invoice not found", "status": 404}
            return {"message": "Sales invoice rejected successfully"}
        except Exception as e:
            log_error(f"Error rejecting sales invoice: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def approve(
        sales_invoice_id: int, 
        tax_invoice_name: Optional[str], 
        user_id: int
    ) -> Dict[str, Any]:
        """
        Approve a sales invoice.
        """
        try:
            query = (
                sales_invoice_tables.update()
                .where(sales_invoice_tables.c.id == sales_invoice_id)
                .values(
                    isApprove=True,
                    updatedAt=dt.now(),
                    updatedBy=user_id,
                    taxInvoiceName=tax_invoice_name
                )
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Sales invoice not found", "status": 404}
            return {"message": "Sales invoice approved successfully"}
        except Exception as e:
            log_error(f"Error approving sales invoice: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def exists(sales_invoice_id: int) -> bool:
        """
        Check if a sales invoice exists.
        """
        try:
            query = select(sales_invoice_tables.c.id).where(
                sales_invoice_tables.c.id == sales_invoice_id
            )
            result = await database.fetch_val(query)
            return result is not None
        except Exception as e:
            log_error(f"Error checking sales invoice existence: {str(e)}")
            return False

    @staticmethod
    async def is_approved_or_deleted(sales_invoice_id: int) -> bool:
        """
        Check if a sales invoice is approved or deleted.
        """
        try:
            query = select(sales_invoice_tables.c.id).where(
                sales_invoice_tables.c.id == sales_invoice_id,
                or_(
                    sales_invoice_tables.c.isApprove == True,
                    sales_invoice_tables.c.isDelete == True
                )
            )
            result = await database.fetch_val(query)
            return result is not None
        except Exception as e:
            log_error(f"Error checking sales invoice status: {str(e)}")
            return False