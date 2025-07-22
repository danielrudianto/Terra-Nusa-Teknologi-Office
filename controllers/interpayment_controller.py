from models.interpayment_model import Interpayment
from models.mutation_model import Mutation
from datetime import datetime as dt

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
            result = await Interpayment.create_interpayment(interpayment_data)
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            
            return {"message": "Interpayment created successfully", "interpaymentID": result.get("interpaymentID")}
        except Exception as e:
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_interpayments(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str):
        """
        Retrieve a list of interpayments from the database.
        """
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            result = await Interpayment.get_interpayments(page, pageSize, filterObject, sortBy, sortByDirection)
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            
            return result
        except Exception as e:
            return {"error": str(e), "status": 500}