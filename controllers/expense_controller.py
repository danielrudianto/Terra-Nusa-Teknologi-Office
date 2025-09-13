from sqlalchemy import insert, select, update, delete, or_, func
from utils.database import database
from models.expense_model import Expense
from typing import Dict, List, Optional
from utils.logger_utils import log_error, log_info
from fastapi import HTTPException
from datetime import datetime
from models.payment_outgoing_model import PaymentOutgoing

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

            expense_id = await Expense.create_expense(expense_data)
            if not isinstance(expense_id, int) and "error" in expense_id:
                log_error(f"Error creating expense: {expense_id['error']}")
                raise HTTPException(status_code=expense_id["status"], detail=expense_id["error"])
            
            return {"message": "Expense created successfully", "expense_id": expense_id}
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
    
    @staticmethod
    async def get_expense_by_id(id: int):
        """
        Retrieve expense data from the database.

        Args:
            id: (int): The ID of the expense

        Returns:
            Dict: A dictionary containing the expense
        """

        expense = await Expense.get_expense_by_id(id)
        if "error" in expense:
            log_error(f"Error retrieving expenses: {expense['error']}")
            raise HTTPException(status_code=expense["status"], detail=expense["error"])
        return expense

    @staticmethod
    async def get_payments_by_expense_id(expense_id: int):
        """
        Get payments by purchase ID.
        
        Args:
            purchase_id (int): The ID of the purchase.
        
        Returns:
            list: A list of payments for the specified purchase.
        """
        log_info(f"Retrieving payments for expense ID: {expense_id}")
        
        try:
            payments = await PaymentOutgoing.get_payments_by_expense_id(expense_id)
            if "error" in payments:
                log_error(f"Error fetching payments for expense ID {expense_id}: {payments['error']}")
                return {"error": payments["error"], "status": payments.get("status", 500)}
            
            log_info(f"Retrieved {len(payments)} payments for expense ID: {expense_id}")
            return payments
        except Exception as e:
            log_error(f"Error retrieving payments: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def approve_expense_by_id(expense_id: int, userID: int):
        try:
            expense = await Expense.get_expense_by_id(expense_id)
            if expense is None or expense["isDelete"] is True:
                log_error(f"Error fetching expense for expense ID {expense_id}: {expense['error']}")
                return {"error": "Expense not found", "status":  404}
            if "error" in expense:
                log_error(f"Error fetching expense for expense ID {expense_id}: {expense['error']}")
                return {"error": expense["error"], "status": expense.get("status", 500)}
            
            await Expense.approve_expense_by_id(expense_id)

            return {
                "message": "Successfully approve expense",
                "expense_id":expense_id
            }
        except Exception as e:
            log_error(f"Error retrieving payments: {str(e)}")
            return {"error": str(e), "status": 500}
