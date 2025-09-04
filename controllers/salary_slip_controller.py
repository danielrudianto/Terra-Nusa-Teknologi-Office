from services.user_service import UserService
from utils.logger_utils import log_error, log_info
from fastapi import HTTPException
from models.salary_slip_model import SalarySlip, SalarySlipAllowance, SalarySlipDeduction
from datetime import datetime as dt
from models.employee_model import Employee
from models.payment_outgoing_model import PaymentOutgoing

class SalarySlipController:
    @staticmethod
    async def fetch(page: int, pageSize: int, keyword: str):
        try:
            result = await SalarySlip.fetch(page, pageSize, keyword)
            if "error" in result:
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return result
        except Exception as e:
            log_error(f"Unexpected error during fetch: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")
    
    @staticmethod
    async def fetchByID(id: int):
        try:
            result = await SalarySlip.fetch_salary_slip_by_id(id)
            if "error" in result:
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            payments = await PaymentOutgoing.get_payments_by_salary_slip_id(id)
            if "error" in payments:
                raise HTTPException(status_code=payments["status"], detail=payments["error"])

            return {
                "data": result,
                "payments": payments
            }
        except Exception as e:
            log_error(f"Unexpected error during fetching by ID {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def delete(id: int, userID: int):
        try:
            result = await SalarySlip.fetch_salary_slip_by_id(id)
            if "error" in result:
                raise HTTPException(status_code=result["status"], detail=result["error"])

            if result is None or result['isDelete'] is True:
                raise HTTPException(status_code=404, detail="Salary slip not found")
            
            deleteResult = await SalarySlip.deleteByID(id, userID)
            if "error" in deleteResult:
                raise HTTPException(status_code=deleteResult["status"], detail=deleteResult["error"])
            
            return deleteResult
        except Exception as e:
            log_error(f"Unexpected error during validation: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def check(userID: int, month: int, year: int):
        try:
            validation = await SalarySlip.validate(userID, month, year)
            if "error" in validation:
                return validation
            
            return {"message": "Validation successful."}
        except Exception as e:
            log_error(f"Unexpected error during validation: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")
        
    @staticmethod
    async def create(userID: int, salarySlip: dict):
        try:
            month = salarySlip.get('month')
            year = salarySlip.get('year')
            employeeID = salarySlip.get('userID')

            if not month or not year:
                return {"error": "Month and year are required.", "status": 400}
            
            # Validate the salary slip data
            validation = await SalarySlip.validate(employeeID, month, year)
            if "error" in validation:
                return {"error": validation["error"], "status": validation["status"]}
            
            salarySlipData = SalarySlip(**salarySlip)
            salarySlipData.createdBy = userID
            salarySlipData.createdAt = dt.now()
            # Create the salary slip
            created_slip = await SalarySlip.create(salarySlipData)
            if not isinstance(created_slip, int) and "error" in created_slip:
                log_error(f"Error creating salary slip: {created_slip['error']}")
                return {"error": created_slip["error"], "status": created_slip["status"]}
            
            await SalarySlipAllowance.create_allowances(created_slip, salarySlip['otherAllowances'])
            await SalarySlipDeduction.create_deductions(created_slip, salarySlip['deductions'])
            log_info(f"Salary slip created successfully for user {userID} for month {month} and year {year}.")
            
            log_info(f"Updating user {userID} taxCategory, position, and department")
            department = salarySlip.get('department')
            position = salarySlip.get('position')
            taxCategory = salarySlip.get('taxCategory')
            userID = salarySlip.get('userID')
            
            
            updated_employee = await Employee.update_detail(userID, taxCategory, position, department)
            if "error" in updated_employee:
                log_error(f"Error updating employee {userID}: {updated_employee['error']}")
                return {"error": updated_employee["error"], "status": updated_employee["status"]}
            
            log_info(f"Successfully updated employee {userID} taxCategory, position, and department")
            return {"message": "Salary slip created successfully.", "salarySlipID": created_slip}
        except HTTPException as e:
            log_error(f"HTTPException during creation: {str(e.detail)}")
            raise e