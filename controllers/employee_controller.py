from utils.database import database
from models.employee_model import Employee
from typing import Dict
from utils.logger_utils import log_error, log_info
from fastapi import HTTPException
from datetime import datetime as dt

class EmployeeController:
    async def create_employee(employee_data: Dict, userID: int) -> Dict:
        """
        Create a new employee in the database.

        Args:
            employee_data (Dict): The data of the expense to create.
            userID (int): The ID of the user creating the expense.

        Returns:
            Dict: A success message with the created expense ID.
        """
        log_info(f"Creating expense with data: {employee_data}")
        try:
            employee_data["createdAt"] = dt.now()
            employee_data["createdBy"] = userID

            result = await Employee(**employee_data).create_employee()
            if "error" in result:
                log_error(f"Error creating expense: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return result
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")
        
    async def get_employees(keyword: str, page: int, pageSize: int = 10, sortBy: str = None, sortByDirection: str = "asc") -> Dict:
        """
        Retrieve a list of employees from the database.

        Args:
            page (int): The page number for pagination.
            pageSize (int): The number of employees per page.
            sortBy (str): The field to sort by.
            sortByDirection (str): The direction to sort (asc/desc).
            keyword (Optional[str]): A keyword to filter employees.

        Returns:
            Dict: A dictionary containing the list of employees and total count.
        """
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
            
        
        log_info(f"Retrieving employees with page={page}, keyword={keyword}")

        if sortBy is None:
            sortBy = "name"
            sortByDirection = "asc"

        employees = await Employee.get_employees(keyword, page, pageSize, sortBy, sortByDirection)
        if "error" in employees:
            log_error(f"Error retrieving employees: {employees['error']}")
            raise HTTPException(status_code=employees["status"], detail=employees["error"])
        
        return employees
    
    async def get_employee_by_id(employee_id: int) -> Employee:
        """
        Get an employee by ID from the database.

        Args:
            employee_id (int): The ID of the employee to fetch.

        Returns:
            Employee: The employee data.
        """
        log_info(f"Fetching employee with ID: {employee_id}")
        try:
            employee = await Employee.get_employee_by_id(employee_id)
            if "error" in employee:
                log_error(f"Error fetching employee: {employee['error']}")
                raise HTTPException(status_code=employee["status"], detail=employee["error"])
            return employee
        except Exception as e:
            log_error(f"Error fetching employee: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")
        
    async def update_employee(employee_data: Dict, userID: int) -> Dict:
        """
        Update an existing employee in the database.

        Args:
            employee_data (Dict): The data of the employee to update.
            userID (int): The ID of the user updating the employee.

        Returns:
            Dict: A success message with the updated employee ID.
        """
        log_info(f"Updating employee with data: {employee_data}")
        try:
            existing_employee_data = await Employee.get_employee_by_id(employee_data["id"])
            if existing_employee_data is None:
                log_error("Employee not found for update.")
                return {"error": "Employee not found.", "status": 404}
            if existing_employee_data.isDelete:
                log_error("Cannot update a deleted employee.")
                return {"error": "Cannot update a deleted employee.", "status": 400}
            
            updated_employee_data = Employee(**employee_data)
            updated_employee_data.updatedBy = userID
            updated_employee_data.updatedAt = dt.now()

            result = await updated_employee_data.update_employee()
            if "error" in result:
                log_error(f"Error updating employee: {result['error']}")
                return {"error": result["error"], "status": result["status"]}
            
            return result
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")