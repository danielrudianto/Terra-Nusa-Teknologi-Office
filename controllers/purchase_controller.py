from repository.purchase_repository import PurchaseRepository, PurchaseStatusRepository
from models.payment_outgoing_model import PaymentOutgoing
from repository.payment_outgoing_repository import PaymentOutgoingRepository
from models.mutation_model import Mutation
from repository.reimbursement_repository import ReimbursementRepository
from repository.sales_invoice_repository import SalesInvoiceRepository
from models.purchase_draft_model import PurchaseDraft
from utils.logger_utils import log_error, log_info
from fastapi import HTTPException
from datetime import datetime

class PurchaseController:
    @staticmethod
    async def create_purchase(purchase_data: dict, userID: int):
        """
        Create a new purchase.
        """
        try:
            purchase_data["createdBy"] = userID
            purchase_data["createdAt"] = datetime.now()
            purchase_data['isDelete'] = False
            purchase_data["isPaid"] = True if purchase_data.get("isInternal") == True else False
            
            lastStatus = purchase_data["lastStatus"]
            lastStatusDescription = purchase_data["lastStatusDescription"]
            
            purchase_id = await PurchaseRepository.create(purchase_data)
            if isinstance(purchase_id, dict) and "error" in purchase_id:
                log_error(f"Error creating purchase: {purchase_id['error']}")
                raise HTTPException(status_code=purchase_id["status"], detail=purchase_id["error"])
            
            log_info(f"Purchase created successfully with ID: {purchase_id}")
            
            # Insert the initial status if the lastStatus is "draft"
            if lastStatus == "draft":
                purchase_status_id = await PurchaseStatusRepository.create({
                    "purchaseID": purchase_id,
                    "status": "draft",
                    "createdAt": purchase_data["createdAt"],
                    "description": lastStatusDescription,
                    "createdBy": userID
                })
                if isinstance(purchase_status_id, dict) and "error" in purchase_status_id:
                    log_error(f"Error creating purchase status: {purchase_status_id['error']}")
                    # Don't fail the whole operation if status creation fails
                    log_info("Purchase created but status creation failed")
            
            return {"message": "Purchase created successfully", "purchase_id": purchase_id}
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error creating purchase: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @staticmethod
    async def check_purchase(invoiceName: str, purchaseOrderName: str):
        """
        Check if a purchase exists with the given invoice name and purchase order name.
        """
        try:
            result = await PurchaseRepository.check_exists(invoiceName, purchaseOrderName)
            if "error" in result:
                log_error(f"Error checking purchase: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error checking purchase: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_purchases(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None):
        """
        Get purchases with pagination and filtering.
        """
        if page < 0:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            result = await PurchaseRepository.get_all(page, pageSize, filterObject, sortBy, sortByDirection, keyword)
            if "error" in result:
                log_error(f"Error fetching purchases: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error fetching purchases: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_purchase_by_id(purchaseID: int):
        """
        Get a purchase by ID.
        """
        try:
            result = await PurchaseRepository.get_by_id(purchaseID)
            payments = await PaymentOutgoingRepository.get_payments_by_purchase_id(purchaseID)
            if "error" in result:
                log_error(f"Error fetching purchase: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            return {
                "purchase": result,
                "payments": payments
            }
        except Exception as e:
            log_error(f"Error fetching purchase: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_purchases_by_purchase_order_name(purchase_order_name: str):
        """
        Get purchases by purchase order name.
        """
        try:
            result = await PurchaseRepository.get_purchases_by_purchase_order_name(purchase_order_name)
            if "error" in result:
                log_error(f"Error fetching purchases: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error fetching purchases: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_payments_by_purchase_id(purchaseID: int):
        """
        Get payments by purchase ID, together with the purchase detail
        (including supplier info) so the client can render the header.
        Returns { "purchase": <detail>, "payments": [...] }.
        """
        try:
            payments = await PaymentOutgoingRepository.get_payments_by_purchase_id(purchaseID)
            if isinstance(payments, dict) and "error" in payments:
                log_error(f"Error fetching payments by purchase ID: {payments['error']}")
                raise HTTPException(status_code=payments["status"], detail=payments["error"])

            purchase = await PurchaseRepository.get_by_id(purchaseID)
            if purchase is None:
                raise HTTPException(status_code=404, detail="Purchase not found")
            if isinstance(purchase, dict) and "error" in purchase:
                raise HTTPException(
                    status_code=purchase.get("status", 500),
                    detail=purchase["error"],
                )

            # The client reads flat fields (supplier_name, supplier_prefix, ...)
            # while get_by_id returns a nested `supplier` object. Provide both.
            purchase = dict(purchase)
            supplier = purchase.get("supplier") or {}
            purchase.setdefault("supplier_name", supplier.get("name"))
            purchase.setdefault("supplier_prefix", supplier.get("prefix"))
            purchase.setdefault("supplier_address", supplier.get("address"))
            purchase.setdefault("supplier_city", supplier.get("city"))
            purchase.setdefault("supplier_province", supplier.get("province"))

            return {
                "purchase": purchase,
                "payments": payments,
            }
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error fetching payments by purchase ID: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_frequent_payment_by_supplier_id(supplierID: int):
        """
        Get frequent payment by supplier ID.
        """
        try:
            result = await PurchaseRepository.get_frequent_payment_by_supplier_id(supplierID)
            if "error" in result:
                log_error(f"Error fetching frequent payment by supplier ID: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            print(result)
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error fetching frequent payment by supplier ID: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_purchase_report_by_project(projectName: str):
        """
        Get purchase report by project.
        """
        try:
            purchases = await PurchaseRepository.get_by_project(projectName)
            if "error" in purchases:
                log_error(f"Error fetching purchase report by project: {purchases['error']}")
                raise HTTPException(status_code=purchases["status"], detail=purchases["error"])
            
            reimbursements = await ReimbursementRepository.get_by_project(projectName)
            if "error" in reimbursements:
                log_error(f"Error fetching purchase report by project: {reimbursements['error']}")
                raise HTTPException(status_code=reimbursements["status"], detail=reimbursements["error"])
            
            purchase_drafts = await PurchaseDraft.get_by_project(projectName)
            if "error" in purchase_drafts:
                log_error(f"Error fetching purchase report by project: {purchase_drafts['error']}")
                raise HTTPException(status_code=purchase_drafts["status"], detail=purchase_drafts["error"])
            
            sales_invoices = await SalesInvoiceRepository.get_by_project(projectName)
            if "error" in sales_invoices:
                log_error(f"Error fetching purchase report by project: {sales_invoices['error']}")
                raise HTTPException(status_code=sales_invoices["status"], detail=sales_invoices["error"])

            
            return {
                "purchases": purchases,
                "reimbursements": reimbursements,
                "purchase_drafts": purchase_drafts,
                "sales_invoices": sales_invoices
            }
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error fetching purchase report by project: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def update_status(purchaseStatus: dict, userID: int):
        """
        Update purchase status.
        """
        try:
            purchase_id = purchaseStatus["id"]

            # Get the purchase first to check if it exists and validate
            purchase = await PurchaseRepository.get_by_id(purchase_id)
            if "error" in purchase:
                log_error(f"Error fetching purchase: {purchase['error']}")
                raise HTTPException(status_code=purchase["status"], detail=purchase["error"])

            if purchase.get("isDelete"):
                return {"error": "Purchase is deleted", "status": 400}
            if purchase.get("lastStatus") == "ready":
                return {"error": "Purchase is already ready", "status": 400}
            
            # Update the purchase status
            result = await PurchaseRepository.update_status(purchase_id, purchaseStatus, userID)
            if "error" in result:
                log_error(f"Error updating purchase status: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            # Create the new status record
            status_result = await PurchaseStatusRepository.create({
                "purchaseID": purchase_id,
                "status": "ready",
                "createdAt": datetime.now(),
                "description": None,
                "createdBy": userID,
            })
            if isinstance(status_result, dict) and "error" in status_result:
                log_error(f"Error creating purchase status: {status_result['error']}")
                # Don't fail the whole operation if status creation fails
                log_info("Purchase updated but status creation failed")
            
            return {"message": "Purchase status updated successfully"}
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error updating purchase status: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @staticmethod
    async def delete_purchase(purchaseID: int, userID: int):
        """
        Delete a purchase.
        """
        try:
            log_info(f"Attempting to delete purchase with ID: {purchaseID} by user ID: {userID}")
            
            # Check if the purchase exists
            purchase = await PurchaseRepository.get_by_id(purchaseID)
            if "error" in purchase:
                log_error(f"Error fetching purchase: {purchase['error']}")
                raise HTTPException(status_code=purchase["status"], detail=purchase["error"])
            
            if purchase.get("isDelete"):
                return {"error": "Purchase is already deleted", "status": 400}
            
            # Delete the purchase
            result = await PurchaseRepository.delete(purchaseID, userID)
            if "error" in result:
                log_error(f"Error deleting purchase: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            log_info(f"Purchase with ID: {purchaseID} deleted successfully by user ID: {userID}")

            # Delete payments associated with the purchase
            payments_result = await PaymentOutgoingRepository.delete_payment_by_purchase_id(purchaseID, userID)
            if "error" in payments_result:
                log_error(f"Error deleting payments for purchase ID {purchaseID}: {payments_result['error']}")
                # Don't fail the whole operation if payment deletion fails
                log_info(f"Purchase deleted but payment deletion failed for purchase ID {purchaseID}")

            # Get payments history for mutation deletion
            payments_history = await PaymentOutgoingRepository.get_payments_by_purchase_id(purchaseID)
            if not isinstance(payments_history, dict) or "error" not in payments_history:
                log_info(f"Fetching payments history for purchase ID: {purchaseID}")
                
                # Delete mutations associated with the payments
                payment_ids = [payment["id"] for payment in payments_history] if payments_history else []
                if payment_ids:
                    mutation_result = await Mutation.delete_mutations_by_payment_ids(payment_ids)
                    if "error" in mutation_result:
                        log_error(f"Error deleting mutations for payments of purchase ID {purchaseID}: {mutation_result['error']}")
                        # Don't fail the whole operation if mutation deletion fails
                        log_info(f"Purchase deleted but mutation deletion failed for purchase ID {purchaseID}")

            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error deleting purchase: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")