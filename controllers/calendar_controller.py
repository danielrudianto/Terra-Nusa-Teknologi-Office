from utils.logger_utils import log_info, log_error
from models.payment_outgoing_model import PaymentOutgoing
from repository.interpayment_repository import InterpaymentRepository
from models.payment_incoming_model import PaymentIncoming
from models.mutation_model import Mutation
from typing import List

class CalendarController:
    @staticmethod
    async def get_calendar_data(month: int, year: int, bankAccounts: List[int]):
        """
        Get calendar data for payments in a specific month and year.
        
        Args:
            month (int): The month for which to retrieve payment data.
            year (int): The year for which to retrieve payment data.
        
        Returns:
            dict: A dictionary containing the calendar data for payments.
        """
        log_info(f"Retrieving calendar data for payments for month: {month}, year: {year}")
        
        try:
            payments = await PaymentOutgoing.get_calendar_data(month, year, bankAccounts)
            if "error" in payments:
                log_error(f"Error fetching calendar data: {payments['error']}")
                return {"error": payments["error"], "status": payments.get("status", 500)}
            
            interpayments = await InterpaymentRepository.get_calendar_data(month, year, bankAccounts)
            if "error" in interpayments:
                log_error(f"Error fetching interpayment calendar data: {interpayments['error']}")
                return {"error": interpayments["error"], "status": interpayments.get("status", 500)}
            
            incomes = await PaymentIncoming.get_calendar_data(month, year, bankAccounts)
            if "error" in incomes:
                log_error(f"Error fetching incoming payment calendar data: {incomes['error']}")
                return {"error": incomes["error"], "status": incomes.get("status", 500)}
            
            balances = await Mutation.fetch_by_month_year(month, year, bankAccounts)
            if isinstance(balances, dict) and "error" in incomes:
                log_error(f"Error fetching incoming payment calendar data: {incomes['error']}")
                return {"error": incomes["error"], "status": incomes.get("status", 500)}
            
            return {
                "payments": payments,
                "incomes": incomes,
                "interpayments": interpayments,
                "balances": balances
            }
        except Exception as e:
            log_error(f"Error retrieving calendar data: {str(e)}")
            return {"error": str(e), "status": 500}