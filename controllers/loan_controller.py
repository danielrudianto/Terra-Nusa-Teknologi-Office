from typing import Dict, Optional
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from datetime import datetime as dt
from repository.loan_repository import LoanRepository
from repository.payment_income_repository import PaymentIncomingRepository

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

            loan_id = result["loan_id"]
            log_info(f"Loan created successfully with ID: {loan_id}")

            # Otomatis catat dana yang DITERIMA (received) sebagai payment_incoming,
            # terhubung ke loan ini, dengan tanggal sesuai tanggal loan.
            try:
                payment_data = {
                    "date": loan_data["date"],
                    "amount": loan_data.get("received", 0) or 0,
                    "loanID": loan_id,
                    "bankAccountID": loan_data.get("bankAccountID"),
                    "createdBy": user_id,
                    "createdAt": dt.now(),
                    "isApprove": True,
                }
                payment_result = await PaymentIncomingRepository.create(payment_data)
                if "error" in payment_result:
                    # Loan tetap berhasil; kegagalan payment_incoming hanya dicatat.
                    log_error(
                        f"Loan {loan_id} created but auto payment_incoming failed: {payment_result['error']}"
                    )
            except Exception as pay_err:
                log_error(
                    f"Loan {loan_id} created but auto payment_incoming raised: {str(pay_err)}"
                )

            return {"message": "Loan created successfully", "loan_id": loan_id}
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
            if isinstance(result, dict) and "error" in result:
                raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
            return result
        except HTTPException as e:
            raise e
        except Exception as e:
            log_error(f"Unexpected error getting loan by ID: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @staticmethod
    async def get_payments_by_loan_id(loan_id: int):
        """Get active outgoing payments for a specific loan."""
        try:
            result = await LoanRepository.get_payments_by_loan_id(loan_id)
            if isinstance(result, dict) and "error" in result:
                raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
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