from repository.income_repository import IncomeRepository
from models.payment_incoming_model import PaymentIncoming
from datetime import datetime as dt
from utils.logger_utils import log_info, log_error
from fastapi import HTTPException
from schemas.income_schema import IncomeCreate

class IncomeController:
    """
    Controller for handling income related operations.
    """

    @staticmethod
    async def create_income(income_data: dict, userID: int):
        """
        Create an income in the database.
        """
        log_info(f"Creating income with data: {income_data}")
        try:
            income_data["createdAt"] = dt.now()
            income_data["createdBy"] = userID
            income_data["isDelete"] = False
            
            result = await IncomeRepository.create(income_data)
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            
            return {"message": "Income created successfully", "incomeID": result.get("incomeID")}
        except Exception as e:
            log_error(f"Unexpected error creating income: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_income(page: int, pageSize: int, sortBy: str, start: str, end: str, sortByDirection: str, keyword: str | None, ignore: bool):
        """
        Get incomes with pagination and filtering.
        """
        if page < 0:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        log_info(f"Retrieving income with page={page}, pageSize={pageSize}, sortBy={sortBy}, sortByDirection={sortByDirection}, keyword={keyword}")
        
        #Convert the start date from "yyyy-mm-dd" to datetime object
        startDate = dt.strptime(start, "%Y-%m-%d")
        endDate = dt.strptime(end, "%Y-%m-%d")
        result = await IncomeRepository.get_all(page, pageSize, sortBy, startDate, endDate, sortByDirection, keyword, ignore)
        if "error" in result:
            log_error(f"Error retrieving incomes: {result['error']}")
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result

    @staticmethod
    async def get_income_by_id(income_id: int):
        """
        Get a single income by ID.
        """
        log_info(f"Retrieving income with ID: {income_id}")
        
        result = await IncomeRepository.get_by_id(income_id)
        payment_incoming = await PaymentIncoming.get_payments_by_income_id(income_id)
        if "error" in result:
            log_error(f"Error retrieving income: {result['error']}")
            raise HTTPException(status_code=result["status"], detail=result["error"])
        
        return {
            "income": result,
            "payment_incoming": payment_incoming
        }

    @staticmethod
    async def update_income(income_id: int, income_data: dict, user_id: int):
        """
        Update an income in the database.
        """
        log_info(f"Updating income {income_id} with data: {income_data}")
        
        # Add updated timestamp
        income_data["updatedAt"] = dt.now()
        income_data["updatedBy"] = user_id
        
        result = await IncomeRepository.update(income_id, income_data)
        if "error" in result:
            log_error(f"Error updating income: {result['error']}")
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result

    @staticmethod
    async def delete_income(income_id: int, user_id: int):
        """
        Delete an income from the database.
        """
        log_info(f"Deleting income with ID: {income_id}")
        
        result = await IncomeRepository.delete(income_id, user_id)
        if "error" in result:
            log_error(f"Error deleting income: {result['error']}")
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result