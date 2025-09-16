from sqlalchemy import func, insert, select, update, delete, or_
from utils.database import database
from models.payment_incoming_model import PaymentIncoming
from utils.logger_utils import log_error, log_info
from datetime import datetime as dt, date as d
from fastapi import HTTPException
from typing import List
from functools import reduce
from datetime import date


def add(x, y):
    return x + y.amount

class PaymentIncomingController:
    @staticmethod
    async def create_payment(payment_data: dict, userID: int):
        """
        Create a new payment in the database.
        
        Args:
            payment_data (dict): The data of the payment to create.
            userID (int): The ID of the user creating the payment.
        
        Returns:
            dict: A success message with the created payment ID.
        """
        payment_data["createdBy"] = userID
        payment_data["createdAt"] = dt.now()
        log_info(f"Creating payment with data: {payment_data}")
        
        try:
            result = await PaymentIncoming.create(payment_data)
            if "error" in result:
                log_error(f"Error creating payment: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error creating payment: {str(e)}")
            return {"error": str(e), "status": 500}