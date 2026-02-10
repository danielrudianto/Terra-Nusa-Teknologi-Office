from services.user_service import UserService
from utils.logger_utils import log_error, log_info
from fastapi import HTTPException
from schemas.salary_slip_schema import SalarySlipCreate
from repository.salary_slip_repository import SalarySlipRepository, SalarySlipAllowanceRepository, SalarySlipDeductionRepository
from datetime import datetime as dt
from models.employee_model import Employee
from models.payment_outgoing_model import PaymentOutgoing           

class SalarySlipController:
    @staticmethod
    async def fetch(page: int, pageSize: int, keyword: str, month: int, year: int):
        try:
            result = await SalarySlipRepository.fetch(page, pageSize, keyword, month, year)
            if "error" in result:
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return result
        except Exception as e:
            log_error(f"Unexpected error during fetch: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")
    
    @staticmethod
    async def fetchByID(id: int):
        try:
            result = await SalarySlipRepository.get_by_id(id)
            if "error" in result:
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            allowances = await SalarySlipRepository.get_allowances_by_salary_slip_id(id)
            if "error" in allowances:
                raise HTTPException(status_code=allowances["status"], detail=allowances["error"])

            deductions = await SalarySlipRepository.get_deductions_by_salary_slip_id(id)
            if "error" in deductions:
                raise HTTPException(status_code=deductions["status"], detail=deductions["error"])

            payments = await PaymentOutgoing.get_payments_by_salary_slip_id(id)
            if "error" in payments:
                raise HTTPException(status_code=payments["status"], detail=payments["error"])

            return {
                "data": result,
                "allowances": allowances,
                "deductions": deductions,
                "payments": payments
            }
        except Exception as e:
            log_error(f"Unexpected error during fetching by ID {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def send(salary_slip_id: int):
        try:
            salarySlip = await SalarySlipRepository.get_by_id(salary_slip_id)
            employeeID = salarySlip.get('userID')

            employee = await Employee.get_employee_by_id(employeeID)
            if "error" in employee:
                raise HTTPException(status_code=employee["status"], detail=employee["error"])
            
            email = employee.get('email')

            
        except Exception as e:
            log_error(f"Unexpected error during send: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def delete(id: int, userID: int):
        try:
            result = await SalarySlipRepository.get_by_id(id)
            if "error" in result:
                raise HTTPException(status_code=result["status"], detail=result["error"])

            if result is None or result.get('isDelete') is True:
                raise HTTPException(status_code=404, detail="Salary slip not found")
            
            deleteResult = await SalarySlipRepository.delete_by_id(id, userID)
            if "error" in deleteResult:
                raise HTTPException(status_code=deleteResult["status"], detail=deleteResult["error"])
            
            return deleteResult
        except Exception as e:
            log_error(f"Unexpected error during validation: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def check(userID: int, month: int, year: int):
        try:
            validation = await SalarySlipRepository.validate(userID, month, year)
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
            validation = await SalarySlipRepository.validate(employeeID, month, year)
            if "error" in validation:
                return {"error": validation["error"], "status": validation["status"]}
            
            # Prepare data for insertion
            salary_slip_data = {
                "userID": salarySlip.get('userID'),
                "month": month,
                "year": year,
                "basicSalary": salarySlip.get('basicSalary'),
                "mealAllowanceQuantity": salarySlip.get('mealAllowanceQuantity', 0.0),
                "mealAllowanceRate": salarySlip.get('mealAllowanceRate', 0.0),
                "transportationAllowanceQuantity": salarySlip.get('transportationAllowanceQuantity', 0.0),
                "transportationAllowanceRate": salarySlip.get('transportationAllowanceRate', 0.0),
                "overtimeQuantity": salarySlip.get('overtimeQuantity', 0.0),
                "overtimeRate": salarySlip.get('overtimeRate', 0.0),
                "taxAmount": salarySlip.get('taxAmount', 0.0),
                "createdAt": dt.now(),
                "updatedAt": dt.now(),
                "createdBy": userID,
                "isPaid": salarySlip.get('isPaid', False),
                "isDelete": False,
                "taxCategory": salarySlip.get('taxCategory'),
                "position": salarySlip.get('position'),
                "department": salarySlip.get('department'),
                "bankAccountName": salarySlip.get('bankAccountName'),
                "bankAccountNumber": salarySlip.get('bankAccountNumber'),
                "bankName": salarySlip.get('bankName'),
                "paymentMethod": salarySlip.get('paymentMethod')
            }

            # Create the salary slip
            created_slip_id = await SalarySlipRepository.create(salary_slip_data)
            if isinstance(created_slip_id, dict) and "error" in created_slip_id:
                log_error(f"Error creating salary slip: {created_slip_id['error']}")
                return {"error": created_slip_id["error"], "status": created_slip_id["status"]}
            
            await SalarySlipAllowanceRepository.create_allowances(created_slip_id, salarySlip.get('otherAllowances', []))
            await SalarySlipDeductionRepository.create_deductions(created_slip_id, salarySlip.get('deductions', []))
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
            return {"message": "Salary slip created successfully.", "salarySlipID": created_slip_id}
        except HTTPException as e:
            log_error(f"HTTPException during creation: {str(e.detail)}")
            raise e