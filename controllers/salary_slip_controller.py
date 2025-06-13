from services.user_service import UserService
from utils.logger_utils import log_error, log_info
from fastapi import HTTPException
from models.salary_slip_model import SalarySlip, SalarySlipAllowance, SalarySlipDeduction
from datetime import datetime as dt

class SalarySlipController:
    @staticmethod
    async def check(userID: int, month: int, year: int):
        try:
            validation = await SalarySlip.validate(userID = userID, month=month, year=year)
            if "error" in validation:
                raise HTTPException(status_code=validation["status"], detail=validation["error"])
            
            return {"message": "Validation successful."}
        except Exception as e:
            # log_error(f"Unexpected error during validation: {str(e)}")
            # raise HTTPException(status_code=500, detail="Internal server error.")
            print("Hi")
        
    @staticmethod
    async def create(userID: int, salarySlip: dict):
        try:
            month = salarySlip.get('month')
            year = salarySlip.get('year')

            if not month or not year:
                return {"error": "Month and year are required.", "status": 400}
            
            # Validate the salary slip data
            validation = await SalarySlip.validate(userID=userID, month=month, year=year)
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
            
            return {"message": "Salary slip created successfully.", "salarySlipID": created_slip}
        except HTTPException as e:
            log_error(f"HTTPException during creation: {str(e.detail)}")
            raise e