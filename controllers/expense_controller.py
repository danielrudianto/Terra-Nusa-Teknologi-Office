from repository.expense_repository import ExpenseRepository
from models.payment_outgoing_model import PaymentOutgoing
from repository.payment_outgoing_repository import PaymentOutgoingRepository
from utils.logger_utils import log_error, log_info
from fastapi import HTTPException
from datetime import datetime as dt

class ExpenseController:
    @staticmethod
    async def create_expense(expense_data: dict, userID: int) -> dict:
        """
        Create a new expense in the database.

        Args:
            expense_data (dict): The data of the expense to create.
            userID (int): The ID of the user creating the expense.

        Returns:
            dict: A success message with the created expense ID.
        """
        log_info(f"Creating expense with data: {expense_data}")
        try:
            expense_data["createdAt"] = dt.now()
            expense_data["createdBy"] = userID
            expense_data['isPaid'] = False
            expense_data['isDelete'] = False

            expense_id = await ExpenseRepository.create(expense_data)
            if isinstance(expense_id, dict) and "error" in expense_id:
                log_error(f"Error creating expense: {expense_id['error']}")
                raise HTTPException(status_code=expense_id["status"], detail=expense_id["error"])
            
            return {"message": "Expense created successfully", "expense_id": expense_id}
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def get_expenses(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None, start: str, end: str, ignore: bool) -> dict:
        """
        Retrieve a list of expenses from the database.

        Args:
            page (int): The page number for pagination.
            pageSize (int): The number of expenses per page.
            filterObject (dict): Filter criteria.
            sortBy (str): The field to sort by.
            sortByDirection (str): The direction to sort (asc/desc).
            keyword (Optional[str]): A keyword to filter expenses.
            start (str): Start date for filtering.
            end (str): End date for filtering.
            ignore (bool): Whether to ignore date filtering.

        Returns:
            dict: A dictionary containing the list of expenses and total count.
        """
        if page < 0:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        log_info(f"Retrieving expenses with page={page}, pageSize={pageSize}, sortBy={sortBy}, sortByDirection={sortByDirection}, keyword={keyword}, start={start}, end={end}")
        
        try:
            # Convert the start date from "yyyy-mm-dd" to datetime object
            startDate = dt.strptime(start, "%Y-%m-%d")
            endDate = dt.strptime(end, "%Y-%m-%d")
            
            expenses = await ExpenseRepository.get_all(page, pageSize, filterObject, sortBy, sortByDirection, keyword, startDate, endDate, ignore)
            if "error" in expenses:
                log_error(f"Error retrieving expenses: {expenses['error']}")
                raise HTTPException(status_code=expenses["status"], detail=expenses["error"])
            return expenses
        except ValueError as e:
            log_error(f"Invalid date format: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")
    
    @staticmethod
    async def get_expense_by_id(id: int):
        """
        Retrieve expense data from the database.

        Args:
            id (int): The ID of the expense

        Returns:
            dict: A dictionary containing the expense
        """
        try:
            expense = await ExpenseRepository.get_by_id(id)
            if "error" in expense:
                log_error(f"Error retrieving expense: {expense['error']}")
                raise HTTPException(status_code=expense["status"], detail=expense["error"])
        
            payments = await PaymentOutgoingRepository.get_payments_by_expense_id(id)
            if "error" in payments:
                log_error(f"Error retrieving payments for expense ID {id}: {payments['error']}")
                raise HTTPException(status_code=payments["status"], detail=payments["error"])
            
            return {
                "expense": expense,
                "payments": payments
            }
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def get_payments_by_expense_id(expense_id: int):
        """
        Get payments by expense ID.
        
        Args:
            expense_id (int): The ID of the expense.
        
        Returns:
            list: A list of payments for the specified expense.
        """
        log_info(f"Retrieving payments for expense ID: {expense_id}")
        
        try:
            payments = await PaymentOutgoingRepository.get_payments_by_expense_id(expense_id)
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
        """
        Approve an expense by ID.
        """
        try:
            # First check if expense exists
            expense = await ExpenseRepository.get_by_id(expense_id)
            if "error" in expense:
                log_error(f"Error fetching expense for expense ID {expense_id}: {expense['error']}")
                raise HTTPException(status_code=expense["status"], detail=expense["error"])
            
            if expense.get("isDelete") is True:
                return {"error": "Expense not found", "status": 404}

            result = await ExpenseRepository.approve_by_id(expense_id, userID)
            if "error" in result:
                log_error(f"Error approving expense: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return {
                "message": "Successfully approved expense",
                "expense_id": expense_id
            }
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error approving expense: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update_expense(expense_id: int, expense_data: dict, userID: int):
        """
        Update an expense.
        """
        try:
            expense_data["updatedBy"] = userID
            expense_data["updatedAt"] = dt.now()
            
            result = await ExpenseRepository.update(expense_id, expense_data)
            if "error" in result:
                log_error(f"Error updating expense: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error updating expense: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def delete_expense(expense_id: int, userID: int):
        """
        Delete an expense.
        """
        try:
            result = await ExpenseRepository.delete(expense_id, userID)
            if "error" in result:
                log_error(f"Error deleting expense: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error deleting expense: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")