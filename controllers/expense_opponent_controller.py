from repository.expense_opponent_repository import ExpenseOpponentRepository
from utils.logger_utils import log_error, log_info
from fastapi import HTTPException
from datetime import datetime as dt

class ExpenseOpponentController:
    """
    Controller for handling expense opponent related operations.
    """

    @staticmethod
    async def create_expense_opponent(expense_opponent_data: dict, userID: int):
        """
        Create an expense opponent in the database.
        """
        log_info(f"Creating expense opponent with data: {expense_opponent_data}")
        try:
            expense_opponent_data["createdAt"] = dt.now()
            expense_opponent_data["createdBy"] = userID
            expense_opponent_data["isDelete"] = False
            
            result = await ExpenseOpponentRepository.create(expense_opponent_data)
            if "error" in result:
                log_error(f"Error creating expense opponent: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return {"message": "Expense opponent created successfully", "opponent_id": result.get("opponent_id")}
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Unexpected error creating expense opponent: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
        
    @staticmethod
    async def get_expense_opponents(page: int, pageSize: int, sortBy: str | None, sortByDirection: str | None, keyword: str | None):
        """
        Retrieve a list of expense opponents from the database.
        """
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        log_info(f"Retrieving expense opponents with page={page}, pageSize={pageSize}, sortBy={sortBy}, sortByDirection={sortByDirection}, keyword={keyword}")
        
        try:
            result = await ExpenseOpponentRepository.get_all(page, pageSize, sortBy, sortByDirection, keyword)
            if "error" in result:
                log_error(f"Error retrieving expense opponents: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Unexpected error retrieving expense opponents: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_expense_opponent_by_id(opponent_id: int):
        """
        Get an expense opponent by ID.
        """
        log_info(f"Retrieving expense opponent with ID: {opponent_id}")
        
        try:
            result = await ExpenseOpponentRepository.get_by_id(opponent_id)
            if "error" in result:
                log_error(f"Error retrieving expense opponent: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Unexpected error retrieving expense opponent: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def update_expense_opponent(opponent_id: int, opponent_data: dict, userID: int):
        """
        Update an expense opponent.
        """
        log_info(f"Updating expense opponent {opponent_id} with data: {opponent_data}")
        
        try:
            opponent_data["updatedBy"] = userID
            opponent_data["updatedAt"] = dt.now()
            
            result = await ExpenseOpponentRepository.update(opponent_id, opponent_data)
            if "error" in result:
                log_error(f"Error updating expense opponent: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Unexpected error updating expense opponent: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def delete_expense_opponent(opponent_id: int, userID: int):
        """
        Delete an expense opponent.
        """
        log_info(f"Deleting expense opponent with ID: {opponent_id}")
        
        try:
            result = await ExpenseOpponentRepository.delete(opponent_id, userID)
            if "error" in result:
                log_error(f"Error deleting expense opponent: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Unexpected error deleting expense opponent: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def search_expense_opponents(keyword: str, limit: int = 10):
        """
        Search expense opponents by name.
        """
        log_info(f"Searching expense opponents with keyword: {keyword}")
        
        try:
            result = await ExpenseOpponentRepository.search_by_name(keyword, limit)
            if "error" in result:
                log_error(f"Error searching expense opponents: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Unexpected error searching expense opponents: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")