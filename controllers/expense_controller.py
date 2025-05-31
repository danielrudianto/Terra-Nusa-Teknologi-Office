from sqlalchemy import insert, select, update, delete, or_, func
from utils.database import database
from models.expense_model import Expense
from typing import Dict, List, Optional
from utils.logger_utils import log_error, log_info
from fastapi import HTTPException
from datetime import datetime

class ExpenseController:
    @staticmethod
    async def create_expense(expense_data: Dict, userID: int) -> Dict:
        """
        Create a new expense in the database.

        Args:
            expense_data (Dict): The data of the expense to create.
            userID (int): The ID of the user creating the expense.

        Returns:
            Dict: A success message with the created expense ID.
        """
        log_info(f"Creating expense with data: {expense_data}")
        try:
            expense_data["createdAt"] = datetime.now()
            expense_data["createdBy"] = userID

            result = await Expense.create_expense(expense_data)
            if "error" in result:
                log_error(f"Error creating expense: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return result
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def get_expenses(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None) -> Dict:
        """
        Retrieve a list of expenses from the database.

        Args:
            page (int): The page number for pagination.
            pageSize (int): The number of expenses per page.
            sortBy (str): The field to sort by.
            sortByDirection (str): The direction to sort (asc/desc).
            keyword (Optional[str]): A keyword to filter expenses.

        Returns:
            Dict: A dictionary containing the list of expenses and total count.
        """
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        log_info(f"Retrieving expenses with page={page}, pageSize={pageSize}, sortBy={sortBy}, sortByDirection={sortByDirection}, keyword={keyword}")
        expenses = await Expense.get_expenses(page, pageSize, filterObject, sortBy, sortByDirection, keyword)
        if "error" in expenses:
            log_error(f"Error retrieving expenses: {expenses['error']}")
            raise HTTPException(status_code=expenses["status"], detail=expenses["error"])
        return expenses