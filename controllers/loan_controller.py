from typing import Dict, Optional
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from datetime import datetime as dt
from repository.loan_repository import LoanRepository
# Assuming you have a PaymentOutgoing repository for payments
# from repository.payment_outgoing_repository import PaymentOutgoingRepository

class LoanController:
    @staticmethod 
    async def create_loan(loan_data: Dict, user_id: int) -> Dict:
        """Create a new loan."""
        log_info(f"Creating loan with data: {loan_data}")
        try:
            # Add creation metadata
            loan_data["createdAt"] = dt.now()
            loan_data["createdBy"] = user_id
            loan_data["isPaid"] = False

            result = await LoanRepository.create(loan_data)
            if "error" in result:
                log_error(f"Error creating loan: {result['error']}")
                raise HTTPException(status_code=result.get("status", 500), detail=result["error"])

            log_info(f"Loan created successfully with ID: {result['loan_id']}")
            return {"message": "Loan created successfully", "loan_id": result['loan_id']}
        except IntegrityError as e:
            log_error(f"Integrity error: {str(e)}")
            raise HTTPException(status_code=400, detail="Loan already exists.")
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")
    
    @staticmethod
    async def get_loan_by_id(loan_id: int):
        """Get a loan by its ID."""
        try:
            result = await LoanRepository.get_loan_by_id(loan_id)
            if "error" in result:
                raise HTTPException(status_code=result["status"], detail=result["error"])
            return result
        except HTTPException as e:
            raise e
        except Exception as e:
            log_error(f"Unexpected error getting loan by ID: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @staticmethod
    async def get_payments_by_loan_id(loan_id: int):
        """Get payments for a specific loan."""
        try:
            # This would come from your PaymentOutgoing repository
            # For now, returning empty list as placeholder
            # result = await PaymentOutgoingRepository.get_payments_by_loan_id(loan_id)
            result = []  # Placeholder - replace with actual repository call
            
            # if "error" in result:
            #     raise HTTPException(status_code=result["status"], detail=result["error"])
            return result
        except HTTPException as e:
            raise e
        except Exception as e:
            log_error(f"Unexpected error getting payments: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @staticmethod
    async def get_loans(page: int, pageSize: int, isPaid: bool, isUnpaid: bool, sortBy: str, sortByDirection: str, keyword: Optional[str] = None):
        """Get paginated list of loans with filtering and sorting."""
        try:
            result = await LoanRepository.get_loans(page, pageSize, isPaid, isUnpaid, sortBy, sortByDirection, keyword)
            if "error" in result:
                raise HTTPException(status_code=result["status"], detail=result["error"])
            return result
        except HTTPException as e:
            raise e
        except Exception as e:
            log_error(f"Unexpected error getting loans: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def update_payment_status(loan_id: int, status: bool, user_id: int):
        """Update the payment status of a loan."""
        try:
            result = await LoanRepository.update_payment_status(loan_id, status, user_id)
            if "error" in result:
                raise HTTPException(status_code=result["status"], detail=result["error"])
            return result
        except HTTPException as e:
            raise e
        except Exception as e:
            log_error(f"Unexpected error updating payment status: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")