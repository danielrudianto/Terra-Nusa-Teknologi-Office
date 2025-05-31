from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from utils.logger_utils import log_error, log_info
from utils.auth_utils import get_current_user
from models.employee_model import Employee
from controllers.employee_controller import EmployeeController

router = APIRouter()

@router.post("/")
async def create_employee(employee: Employee, user: Annotated[dict, Depends(get_current_user)]):
    """
    Create a new payment. Requires a valid token.
    """
    userID = user["id"]
    result = await EmployeeController.create_employee(employee.model_dump(), userID)
    
    if "error" in result:
        log_error(f"Error creating payment: {result['error']}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return result

@router.get("/{employee_id}")
async def get_employee(employee_id: int, user: Annotated[dict, Depends(get_current_user)]):
    """
    Get an employee by ID. Requires a valid token.
    """
    result = await EmployeeController.get_employee_by_id(employee_id)
    
    if "error" in result:
        log_error(f"Error fetching employee: {result['error']}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result

@router.get("/")
async def get_employees(
    request: Request,
    user: Annotated[dict, Depends(get_current_user)]
):
    """
    Get a list of employees. Requires a valid token.
    """
    keyword = request.query_params.get("keyword")
    page = int(request.query_params.get("page", 1))
    pageSize = int(request.query_params.get("pageSize", 10))
    sortBy = request.query_params.get("sortBy")
    sortByDirection = request.query_params.get("sortByDirection")

    try:
        result = await EmployeeController.get_employees(keyword, page, pageSize, sortBy, sortByDirection)
        if "error" in result:
            raise HTTPException(status_code=result["status"], detail=result["error"])
        return result
    except HTTPException as e:
        # Optionally log the error or handle it differently
        raise e
    
@router.put("/")
async def update_employee(employee: Employee, user: Annotated[dict, Depends(get_current_user)]):
    """
    Update an existing employee. Requires a valid token.
    """
    userID = user["id"]
    result = await EmployeeController.update_employee(employee.model_dump(), userID)
    
    if "error" in result:
        log_error(f"Error updating employee: {result['error']}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    
    return result