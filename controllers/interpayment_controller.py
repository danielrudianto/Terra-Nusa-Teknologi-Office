from repository.interpayment_repository import InterpaymentRepository
from utils.logger_utils import log_error
from datetime import datetime, date as d

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
    async def delete_interpayment(interpaymentID: int, userID: int):
        """
        Delete an interpayment from the database.
        """
        try:
            interpayment = await InterpaymentRepository.get_by_id(interpaymentID)
            if not interpayment:
                return {"error": "Interpayment not found", "status": 404}
            
            #If interpayment is deleted, then return error
            if interpayment["isDelete"]:
                return {"error": "Interpayment already deleted", "status": 400}
            
            #If interpayment is today or later, then proceed the deletation, if it's in the past
            #First convert the interpayment date to datetime object (YYYY-MM-dd)
            #Convert interpayment['date'] from datetime object to 
            
            if interpayment['date'] < d.today():
                return {"error": "Interpayment is in the past", "status": 400}
            
            result = await InterpaymentRepository.delete(interpaymentID, userID)
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            
            return {"message": "Interpayment deleted successfully"}
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