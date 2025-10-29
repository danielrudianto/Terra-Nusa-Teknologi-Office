from repository.interpayment_repository import InterpaymentRepository
from utils.logger_utils import log_error
from datetime import datetime

class InterpaymentController:
    """
    Controller for handling interpayment related operations.
    """

    @staticmethod
    async def create_interpayment(interpayment_data: dict):
        """
        Create an interpayment in the database.
        """
        try:
            interpayment_data["isDelete"] = False
            interpayment_data["createdAt"] = datetime.now()
            
            result = await InterpaymentRepository.create(interpayment_data)
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            
            return {"message": "Interpayment created successfully", "interpaymentID": result.get("interpaymentID")}
        except Exception as e:
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_interpayments(page: int, pageSize: int, start: str, end: str, filterObject: dict, sortBy: str, sortByDirection: str):
        """
        Retrieve a list of interpayments from the database.
        """
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            startDate = datetime.strptime(start, "%Y-%m-%d")
            endDate = datetime.strptime(end, "%Y-%m-%d")
            result = await InterpaymentRepository.get_interpayments(page, pageSize, startDate, endDate, filterObject, sortBy, sortByDirection)
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            
            return result
        except Exception as e:
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_interpayment_calendar_data(month: int, year: int, bankAccountID: list[int]):
        """
        Retrieve a list of interpayments from the database.
        """
        try:
            result = await InterpaymentRepository.get_calendar_data(month, year, bankAccountID)
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            
            return result
        except Exception as e:
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_interpayment_calendar_data_by_date(date: int, month: int, year: int, bankAccountID: list[int] | None):
        """
        Retrieve a list of interpayments from the database.
        """
        try:
            result = await InterpaymentRepository.get_calendar_data_by_date(date, month, year, bankAccountID)
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            
            return result
        except Exception as e:
            return {"error": str(e), "status": 500}