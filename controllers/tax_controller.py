from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from models.purchase_model import Purchase
from models.expense_model import Expense
from models.payment_outgoing_model import PaymentOutgoing

class TaxController:
    @staticmethod
    async def get_ppn_report(month: int, year: int):
        try:
            result = await Purchase.get_ppn_report(month, year)
            if "error" in result:
                log_error(f"Error fetching PPN report: {result['error']}")
                return {"error": result["error"], "status": result["status"]}
            
            return result
        except Exception as e:
            log_error(f"Error fetching purchase PPN: {str(e)}")
            return {"error": str(e), "status": 500}
        
    async def get_pph_report(month: int, year: int):
        log_info(f"Fetching PPh report for month {month} and year {year}")
        try:
            purchases = await PaymentOutgoing.get_purchase_pph_report(month, year)
            if "error" in purchases:
                log_error(f"Error fetching purchase data: {purchases['error']}")
                raise HTTPException(status_code=purchases.get("status", 500), detail=purchases["error"])
            
            expenses = await PaymentOutgoing.get_expense_pph_report(month, year)
            if "error" in expenses:
                log_error(f"Error fetching expense data: {expenses['error']}")
                raise HTTPException(status_code=expenses.get("status", 500), detail=expenses["error"])
            
            return {
                "purchase": purchases,
                "expense": expenses
            }
            
            
        except IntegrityError as e:
            log_error(f"Integrity error: {str(e)}")
            raise HTTPException(status_code=400, detail="Asset already exists.")
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")