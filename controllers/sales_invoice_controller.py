from models.sales_invoice_model import SalesInvoice
from datetime import datetime as dt

class SalesInvoiceController:
    @staticmethod
    async def create_sales_invoice(sales_invoice: dict, userID: int):
        """
        Create a new sales invoice.
        """
        # Placeholder for actual implementation
        # This should interact with the database or service layer to create the invoice

        sales_invoice["createdBy"] = userID
        sales_invoice["createdAt"] = dt.now()
        try:
            result = await SalesInvoice.create_sales_invoice(sales_invoice)
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            return result
        except Exception as e:
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def check_sales_invoice(description: str, projectName: str, clientID: int, name: str):
        """
        Check if a sales invoice with the same description, project name, and client ID already exists.
        """
        try:
            result = await SalesInvoice.get_sales_invoice_by_name(name)
            if result is not None:
                return {"exists": True, "field": "name", "salesInvoiceID": result["id"]}
            
            #Next check if there is any invoice with the same project name, description, and client ID
            result = await SalesInvoice.check_sales_invoice(description, projectName, clientID)
            if result:
                return {"exists": True, "field": "description", "salesInvoiceID": None}
            
            return {"exists": False, "field": None, "salesInvoiceID": None}
        except Exception as e:
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_sales_invoices(page, pageSize):
        """
        Get sales invoices with pagination.
        """
        try:
            result = await SalesInvoice.get_sales_invoices(page, pageSize)
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}  
            return result
        except Exception as e:
            return {"error": str(e), "status": 500}