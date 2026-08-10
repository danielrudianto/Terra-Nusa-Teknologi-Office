from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, or_, and_, desc, asc, extract
from utils.database import database
from utils.logger_utils import log_error
from datetime import datetime as dt
from models.sales_invoice_model import sales_invoice_tables
from models.client_model import clients_table
from models.payment_incoming_model import payment_incoming_table
from schemas.sales_invoice_schema import SalesInvoiceCreate, SalesInvoiceUpdate, SalesInvoiceWithClientResponse

class SalesInvoiceRepository:
    @staticmethod
    def _enrich_with_status(row: dict) -> dict:
        """
        Tambahkan field turunan (computed) ke sebuah invoice:
        - invoiceValue : nilai tagihan = dpp + ppn*dpp/100 - pph*dpp/100 - bpjs (BPJS = potongan)
        - isPaid       : True jika total_paid >= invoiceValue (toleransi Rp 5)
        - taxingStatus : status pajak berdasarkan PPN/PPh/pembayaran

        Aturan taxingStatus:
        1. Ada PPN & taxInvoiceName kosong                -> 'tax_invoice_not_published'
        2. Ada PPh & incomeTaxInvoiceName kosong & sudah dibayar   -> 'income_tax_not_published'
        3. Ada PPh & incomeTaxInvoiceName kosong & belum dibayar   -> 'waiting_for_payment'
        4. Selain itu                                    -> 'fully_published'
        """
        dpp = row.get("dpp") or 0
        ppn = row.get("ppn") or 0
        pph = row.get("pphPercentage") or 0
        bpjs = row.get("bpjs") or 0
        total_paid = row.get("total_paid") or 0

        invoice_value = dpp + (ppn * dpp) / 100 - (pph * dpp) / 100 - bpjs
        is_paid = total_paid >= (invoice_value - 5)  # toleransi pembulatan Rp 5

        has_ppn = ppn and ppn > 0
        has_pph = pph and pph > 0
        tax_invoice_empty = not (row.get("taxInvoiceName") or "").strip()
        income_tax_empty = not (row.get("incomeTaxInvoiceName") or "").strip()

        if has_ppn and tax_invoice_empty:
            status = "tax_invoice_not_published"
        elif has_pph and income_tax_empty:
            status = "income_tax_not_published" if is_paid else "waiting_for_payment"
        else:
            status = "fully_published"

        row["invoiceValue"] = invoice_value
        row["isPaid"] = is_paid
        row["taxingStatus"] = status
        return row

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
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="sales_invoices",
                entityID=result,
                action="create",
            )
            return {"message": "Sales invoice created successfully", "sales_invoice_id": result}
        except Exception as e:
            log_error(f"Error creating sales invoice: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

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
                # NPWP dipakai saat membuat faktur pajak dari layar konfirmasi
                clients_table.c.npwp.label("client_npwp"),
            ]

            # Subquery: total pembayaran yang sudah diterima per invoice (uang masuk)
            payment_subquery = (
                select(
                    payment_incoming_table.c.salesInvoiceID.label("invoice_id"),
                    func.coalesce(
                        func.sum(payment_incoming_table.c.amount), 0
                    ).label("total_paid"),
                )
                .group_by(payment_incoming_table.c.salesInvoiceID)
                .subquery()
            )

            query = (
                select(
                    *sales_invoice_tables.c,
                    *client_columns,
                    func.coalesce(payment_subquery.c.total_paid, 0).label("total_paid"),
                )
                .join(
                    clients_table,
                    sales_invoice_tables.c.clientID == clients_table.c.id,
                )
                .outerjoin(
                    payment_subquery,
                    sales_invoice_tables.c.id == payment_subquery.c.invoice_id,
                )
                .where(
                    sales_invoice_tables.c.projectName == projectName,
                    sales_invoice_tables.c.isDelete == False,
                )
            )

            result = await database.fetch_all(query)
            return [
                SalesInvoiceRepository._enrich_with_status(dict(row))
                for row in result
            ]
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
                # NPWP dipakai saat membuat faktur pajak dari layar konfirmasi
                clients_table.c.npwp.label("client_npwp"),
            ]
            
            query = select(
                *sales_invoice_tables.c,
                *client_columns,
                func.coalesce(
                    select(
                        func.coalesce(func.sum(payment_incoming_table.c.amount), 0)
                    )
                    .where(payment_incoming_table.c.salesInvoiceID == sales_invoice_tables.c.id)
                    .scalar_subquery(),
                    0,
                ).label("total_paid"),
            ).join(
                clients_table, 
                sales_invoice_tables.c.clientID == clients_table.c.id
            ).where(
                sales_invoice_tables.c.id == sales_invoice_id
            )
            
            result = await database.fetch_one(query)
            return SalesInvoiceRepository._enrich_with_status(dict(result)) if result else None
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
                # NPWP dipakai saat membuat faktur pajak dari layar konfirmasi
                clients_table.c.npwp.label("client_npwp"),
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
        keyword: Optional[str] = None,
        filters: Optional[List[str]] = None,
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

            # Subquery: total pembayaran diterima per invoice (untuk isPaid & taxing status)
            payment_subquery = (
                select(
                    payment_incoming_table.c.salesInvoiceID.label("invoice_id"),
                    func.coalesce(
                        func.sum(payment_incoming_table.c.amount), 0
                    ).label("total_paid"),
                )
                .group_by(payment_incoming_table.c.salesInvoiceID)
                .subquery()
            )

            # Expression nilai tagihan & total dibayar (untuk filter)
            si = sales_invoice_tables.c
            invoice_value_expr = (
                si.dpp
                + (si.ppn * si.dpp) / 100
                - (si.pphPercentage * si.dpp) / 100
                - si.bpjs
            )
            total_paid_expr = func.coalesce(payment_subquery.c.total_paid, 0)
            is_paid_expr = total_paid_expr >= (invoice_value_expr - 5)
            has_ppn_expr = si.ppn > 0
            has_pph_expr = si.pphPercentage > 0
            tax_invoice_empty_expr = or_(
                si.taxInvoiceName.is_(None), func.trim(si.taxInvoiceName) == ""
            )
            income_tax_empty_expr = or_(
                si.incomeTaxInvoiceName.is_(None),
                func.trim(si.incomeTaxInvoiceName) == "",
            )

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

            # Filter chip (multi-select -> OR antar chip yang dipilih)
            if filters:
                filter_map = {
                    "paid": is_paid_expr,
                    "unpaid": ~is_paid_expr,
                    # Complete: fully_published -> tidak ada PPN nunggak & tidak ada PPh nunggak
                    "complete": and_(
                        ~and_(has_ppn_expr, tax_invoice_empty_expr),
                        ~and_(has_pph_expr, income_tax_empty_expr),
                    ),
                    # No tax invoice: ada PPN tapi faktur kosong
                    "no_tax_invoice": and_(has_ppn_expr, tax_invoice_empty_expr),
                    # No withholding: ada PPh tapi bukti potong kosong
                    "no_withholding": and_(has_pph_expr, income_tax_empty_expr),
                }
                chip_conditions = [
                    filter_map[f] for f in filters if f in filter_map
                ]
                if chip_conditions:
                    conditions.append(or_(*chip_conditions))

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
                    *client_columns,
                    func.coalesce(payment_subquery.c.total_paid, 0).label("total_paid"),
                )
                .join(clients_table, sales_invoice_tables.c.clientID == clients_table.c.id)
                .outerjoin(
                    payment_subquery,
                    sales_invoice_tables.c.id == payment_subquery.c.invoice_id,
                )
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
                .outerjoin(
                    payment_subquery,
                    sales_invoice_tables.c.id == payment_subquery.c.invoice_id,
                )
                .where(*conditions)
            )

            # Execute queries
            sales_invoices_data = await database.fetch_all(data_query)
            total_count = await database.fetch_val(count_query)

            sales_invoices = [
                SalesInvoiceRepository._enrich_with_status(dict(row))
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
    async def get_monthly_recap(month: int, year: int):
        try:
            client_columns = [
                clients_table.c.name.label("client_name"),
                clients_table.c.id.label("client_id"),
                clients_table.c.address.label("client_address"),
                clients_table.c.city.label("client_city"),
                clients_table.c.province.label("client_province"),
                clients_table.c.prefix.label("client_prefix"),
                # NPWP dipakai saat membuat faktur pajak dari layar konfirmasi
                clients_table.c.npwp.label("client_npwp"),
            ]
            
            query = select(
                *sales_invoice_tables.c,
                *client_columns
            ).join(
                clients_table, 
                sales_invoice_tables.c.clientID == clients_table.c.id
            ).where(
                extract("month", sales_invoice_tables.c.date) == month,
                extract("year", sales_invoice_tables.c.date) == year
            )
            
            result = await database.fetch_all(query)
            if not result:
                return []

            return [
                dict(row)
                for row in result
            ]
        except Exception as e:
            log_error(f"Error fetching sales invoice by name: {str(e)}")
            raise
    
    @staticmethod
    async def get_monthly_ar(month, year):
        """
            The goal is to determine the sales invoice on this month and year, and before that (example, the month and year is 1 and 2026, then search sales invoices that is less than "2026-31-01")
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

            # Subquery total payment per invoice
            payment_subquery = (
                select(
                    payment_incoming_table.c.salesInvoiceID.label("invoice_id"),
                    func.coalesce(func.sum(payment_incoming_table.c.amount), 0).label("total_paid")
                )
                .group_by(payment_incoming_table.c.salesInvoiceID)
                .subquery()
            )

            # Main query
            query = (
                select(
                    clients_table.c.name.label("client_name"),
                    sales_invoice_tables.c.id,
                    sales_invoice_tables.c.name,
                    sales_invoice_tables.c.description,
                    sales_invoice_tables.c.projectName,
                    sales_invoice_tables.c.date,
                    sales_invoice_tables.c.spkNumber,
                    sales_invoice_tables.c.dpp,
                    sales_invoice_tables.c.ppn,
                    sales_invoice_tables.c.pphPercentage,
                    sales_invoice_tables.c.pphCode,
                    sales_invoice_tables.c.pphTaxObject,
                    sales_invoice_tables.c.bpjs,
                    sales_invoice_tables.c.taxInvoiceName,
                    func.coalesce(payment_subquery.c.total_paid, 0).label("total_paid"),

                    (
                        sales_invoice_tables.c.dpp + sales_invoice_tables.c.ppn * sales_invoice_tables.c.dpp / 100 - sales_invoice_tables.c.pphPercentage * sales_invoice_tables.c.dpp / 100 - sales_invoice_tables.c.bpjs -
                        func.coalesce(payment_subquery.c.total_paid, 0)
                    ).label("remaining")
                )
                .outerjoin(
                    payment_subquery,
                    sales_invoice_tables.c.id == payment_subquery.c.invoice_id,
                )
                .join(
                    clients_table,
                    sales_invoice_tables.c.clientID == clients_table.c.id
                )
                .where(
                    sales_invoice_tables.c.date < end_date,
                    sales_invoice_tables.c.isDelete == False,
                    sales_invoice_tables.c.isApprove == True
                )
            )

            results = await database.fetch_all(query)

            ar_list = []

            for row in results:
                data = dict(row)

                # Kalau sisa lebih dari 5 rupiah → AR
                if data["remaining"] is not None and data["remaining"] >= 5:
                    ar_list.append(data)

            return {
                "data": ar_list,
                "count": len(ar_list)
            }

        except Exception as e:
            log_error(f"Error fetching monthly AR: {str(e)}")
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
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="sales_invoices",
                entityID=sales_invoice_id,
                action="reject",
                userID=user_id,
            )
            
            return {"message": "Sales invoice rejected successfully"}
        except Exception as e:
            log_error(f"Error rejecting sales invoice: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def set_tax_invoice_name(
        sales_invoice_id: int, tax_invoice_name: str, user_id: int
    ) -> Dict[str, Any]:
        """Set nomor faktur pajak PPN pada sebuah invoice."""
        try:
            query = (
                sales_invoice_tables.update()
                .where(sales_invoice_tables.c.id == sales_invoice_id)
                .values(
                    taxInvoiceName=tax_invoice_name,
                    updatedAt=dt.now(),
                    updatedBy=user_id,
                )
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Sales invoice not found", "status": 404}
            return {"message": "Tax invoice number saved successfully"}
        except Exception as e:
            log_error(f"Error setting tax invoice name: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def set_income_tax_name(
        sales_invoice_id: int, income_tax_name: str, user_id: int
    ) -> Dict[str, Any]:
        """Set nomor bukti potong PPh pada sebuah invoice."""
        try:
            query = (
                sales_invoice_tables.update()
                .where(sales_invoice_tables.c.id == sales_invoice_id)
                .values(
                    incomeTaxInvoiceName=income_tax_name,
                    updatedAt=dt.now(),
                    updatedBy=user_id,
                )
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Sales invoice not found", "status": 404}
            return {"message": "Income tax slip number saved successfully"}
        except Exception as e:
            log_error(f"Error setting income tax name: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

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
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="sales_invoices",
                entityID=sales_invoice_id,
                action="approve",
                userID=user_id,
            )

            return {"message": "Sales invoice approved successfully"}
        except Exception as e:
            log_error(f"Error approving sales invoice: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

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