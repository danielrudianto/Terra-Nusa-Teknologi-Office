from sqlalchemy import func, insert, select, update, delete, or_
from utils.database import database
from repository.payment_income_repository import PaymentIncomingRepository
from utils.logger_utils import log_error, log_info
from datetime import datetime as dt, date as d
from fastapi import HTTPException
from typing import List
from functools import reduce
from datetime import date
from utils.errors import internal_error

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
        payment_data['createdAt'] = dt.now()
        payment_data['isApprove'] = True
        log_info(f"Creating payment with data: {payment_data}")
        
        try:
            payment = await PaymentIncomingRepository.create(payment_data)
            if "error" in payment:
                log_error(f"Error creating payment: {payment['error']}")
                return {"error": payment["error"], "status": payment.get("status", 500)}
            return payment
        except Exception as e:
            log_error(f"Error creating payment: {str(e)}")
            return internal_error()