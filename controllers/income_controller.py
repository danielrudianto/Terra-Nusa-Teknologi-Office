from models.income_model import Income
from models.mutation_model import Mutation
from datetime import datetime as dt
from utils.logger_utils import log_info, log_error
from fastapi import HTTPException

class IncomeController:
    """
    Controller for handling income related operations.
    """

    @staticmethod
    async def create_income(income_data: dict, userID):
        """
        Create an income in the database.
        """
        log_info(f"Creating income with data: {income_data}")
        try:
            income_data["createdAt"] = dt.now()
            income_data["createdBy"] = userID
            
            income = Income(**income_data)
            result = await income.create()
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            
            return {"message": "Income created successfully", "incomeID": result.get("incomeID")}
        except Exception as e:
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_income(page: int, pageSize: int, sortBy: str, sortByDirection: str, keyword: str | None,):
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        log_info(f"Retrieving income with page={page}, pageSize={pageSize}, sortBy={sortBy}, sortByDirection={sortByDirection}, keyword={keyword}")
        expenses = await Income.get_income(page, pageSize, sortBy, sortByDirection, keyword)
        if "error" in expenses:
            log_error(f"Error retrieving expenses: {expenses['error']}")
            raise HTTPException(status_code=expenses["status"], detail=expenses["error"])
        return expenses