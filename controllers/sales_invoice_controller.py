from typing import Dict, Optional
from utils.logger_utils import log_error, log_info
from fastapi import HTTPException
from schemas.sales_invoice_schema import SalesInvoiceCreate, SalesInvoiceWithPaymentsResponse
from repository.sales_invoice_repository import SalesInvoiceRepository
# Assuming you have a PaymentRepository for payment operations
# from repository.payment_repository import PaymentRepository

class SalesInvoiceController:
    @staticmethod
    async def create_sales_invoice(sales_invoice_data: dict, user_id: int) -> Dict:
        """
        Create a new sales invoice.
        """
        log_info(f"Creating sales invoice with data: {sales_invoice_data}")
        try:
            # Add user ID to sales invoice data
            sales_invoice_data["createdBy"] = user_id
            sales_invoice_data["isApprove"] = False
            
            # Validate and create sales invoice model
            sales_invoice_create = SalesInvoiceCreate(**sales_invoice_data)
            
            # Use repository to create sales invoice
            result = await SalesInvoiceRepository.create(sales_invoice_create)
            
            if "error" in result:
                log_error(f"Error creating sales invoice: {result['error']}")
                raise HTTPException(
                    status_code=result.get("status", 500), 
                    detail=result["error"]
                )

            log_info(f"Sales invoice created successfully with ID: {result['sales_invoice_id']}")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Unexpected error creating sales invoice: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def check_sales_invoice(
        description: str, 
        project_name: str, 
        client_id: int, 
        name: str
    ) -> Dict:
        """
        Check if a sales invoice with the same description, project name, and client ID already exists.
        """
        log_info(f"Checking sales invoice - name: {name}, project: {project_name}, client: {client_id}")
        try:
            # Check by name first
            existing_by_name = await SalesInvoiceRepository.get_by_name(name)
            if existing_by_name:
                return {
                    "exists": True, 
                    "field": "name", 
                    "sales_invoice_id": existing_by_name.id
                }
            
            # Check by description, project name, and client ID
            is_duplicate = await SalesInvoiceRepository.check_duplicate(
                description, project_name, client_id
            )
            if is_duplicate:
                return {
                    "exists": True, 
                    "field": "description", 
                    "sales_invoice_id": None
                }
            
            return {"exists": False, "field": None, "sales_invoice_id": None}
            
        except Exception as e:
            log_error(f"Error checking sales invoice: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_sales_invoices(
        page: int, 
        page_size: int, 
        sort_by: str, 
        sort_direction: str, 
        keyword: Optional[str] = None
    ) -> Dict:
        """
        Get sales invoices with pagination.
        """
        log_info(f"Fetching sales invoices - page: {page}, page_size: {page_size}, keyword: {keyword}")
        try:
            # Validate pagination parameters
            if page < 1:
                raise HTTPException(status_code=400, detail="Page must be greater than 0")
            if page_size < 1 or page_size > 100:
                raise HTTPException(status_code=400, detail="Page size must be between 1 and 100")

            result = await SalesInvoiceRepository.get_paginated(
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_direction=sort_direction,
                keyword=keyword
            )
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error fetching sales invoices: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_sales_invoice_by_id(sales_invoice_id: int) -> Dict:
        """
        Get sales invoice by ID with payments.
        """
        log_info(f"Fetching sales invoice with ID: {sales_invoice_id}")
        try:
            # Validate sales invoice ID
            if sales_invoice_id < 1:
                raise HTTPException(status_code=400, detail="Sales invoice ID must be greater than 0")

            # Get sales invoice with client information
            sales_invoice = await SalesInvoiceRepository.get_by_id(sales_invoice_id)
            if not sales_invoice:
                raise HTTPException(status_code=404, detail="Sales invoice not found")

            # Get payments for this sales invoice
            # Assuming you have a PaymentRepository
            # payments = await PaymentRepository.get_by_sales_invoice_id(sales_invoice_id)
            payments = []  # Placeholder - replace with actual payment retrieval

            # Combine sales invoice and payments
            response_data = SalesInvoiceWithPaymentsResponse(
                **sales_invoice.model_dump(),
                payments=payments
            )

            log_info(f"Successfully fetched sales invoice with ID: {sales_invoice_id}")
            return response_data.model_dump()
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error fetching sales invoice {sales_invoice_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def reject_sales_invoice(sales_invoice_id: int, user_id: int) -> Dict:
        """
        Reject sales invoice by ID.
        """
        log_info(f"Rejecting sales invoice with ID: {sales_invoice_id}")
        try:
            # Validate sales invoice ID
            if sales_invoice_id < 1:
                raise HTTPException(status_code=400, detail="Sales invoice ID must be greater than 0")

            # Check if sales invoice exists and is not already approved/deleted
            if await SalesInvoiceRepository.is_approved_or_deleted(sales_invoice_id):
                raise HTTPException(
                    status_code=400, 
                    detail="Sales invoice has been confirmed or deleted"
                )

            # Reject the sales invoice
            result = await SalesInvoiceRepository.reject(sales_invoice_id, user_id)
            
            if "error" in result:
                log_error(f"Error rejecting sales invoice: {result['error']}")
                raise HTTPException(
                    status_code=result.get("status", 500), 
                    detail=result["error"]
                )

            log_info(f"Successfully rejected sales invoice with ID: {sales_invoice_id}")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error rejecting sales invoice {sales_invoice_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def approve_sales_invoice(
        sales_invoice_id: int, 
        tax_invoice_name: Optional[str], 
        user_id: int
    ) -> Dict:
        """
        Approve sales invoice by ID.
        """
        log_info(f"Approving sales invoice with ID: {sales_invoice_id}")
        try:
            # Validate sales invoice ID
            if sales_invoice_id < 1:
                raise HTTPException(status_code=400, detail="Sales invoice ID must be greater than 0")

            # Check if sales invoice exists and is not already approved/deleted
            if await SalesInvoiceRepository.is_approved_or_deleted(sales_invoice_id):
                raise HTTPException(
                    status_code=400, 
                    detail="Sales invoice has been confirmed or deleted"
                )

            # Approve the sales invoice
            result = await SalesInvoiceRepository.approve(
                sales_invoice_id, tax_invoice_name, user_id
            )
            
            if "error" in result:
                log_error(f"Error approving sales invoice: {result['error']}")
                raise HTTPException(
                    status_code=result.get("status", 500), 
                    detail=result["error"]
                )

            log_info(f"Successfully approved sales invoice with ID: {sales_invoice_id}")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error approving sales invoice {sales_invoice_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")