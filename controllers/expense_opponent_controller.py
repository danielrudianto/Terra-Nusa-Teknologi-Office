from models.expense_opponent_model import ExpenseOpponent
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
        try:
            expense_opponent_data["createdAt"] = dt.now()
            expense_opponent_data["createdBy"] = userID
            result = await ExpenseOpponent.create_expense_opponent(expense_opponent_data)
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            
            return {"message": "Expense opponent created successfully"}
        except Exception as e:
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_expense_opponents(page: int, pageSize: int, sortBy: str | None, sortByDirection: str | None, keyword: str | None):
        """
        Retrieve a list of expense opponents from the database.
        """
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            result = await ExpenseOpponent.get_expense_opponents(page, pageSize, sortBy, sortByDirection, keyword)
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            
            return result
        except Exception as e:
            return {"error": str(e), "status": 500}