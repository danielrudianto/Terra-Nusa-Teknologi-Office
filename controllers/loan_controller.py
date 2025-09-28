from typing import Dict, List, Optional
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from datetime import datetime as dt, date as d
from utils.redis import r
from models.loans_model import Loans

class LoanController:
    @staticmethod 
    async def create_loan(loan_data: Dict, userID: int) -> Dict:
        """
        Create a new loan data.
        
        Args:
            loan_data (Dict): The data of the loan to create.
        
        Returns:
            Dict: A success message with the created loan ID.
        """
        log_info(f"Creating loan with data: {loan_data}")
        try:
            # Create new Bank model

            loan_data["createdAt"] = dt.now()
            loan_data["createdBy"] = userID

            loan = Loans(**loan_data)
            result = await loan.create()
            if "error" in result:
                log_error(f"Error creating loan: {result['error']}")
                raise HTTPException(status_code=result.get("status", 500), detail=result["error"])

            log_info(f"Loan created successfully with ID: {result['loan_id']}")
            return {"message": "Loan created successfully", "loan_id": result['loan_id']}
        except IntegrityError as e:
            log_error(f"Integrity error: {str(e)}")
            raise HTTPException(status_code=400, detail="Bank account already exists.")
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")