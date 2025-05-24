from sqlalchemy import func, insert, select, update, delete, or_
from utils.database import database
from models.purchase_model import purchases_table, purchase_status_table
from models.supplier_model import suppliers_table
from utils.logger_utils import log_error, log_info
from datetime import datetime

class PaymentController:
    @staticmethod
    async def get_all_payments(page: int = 1, limit: int = 10) -> Dict:
        """
        Retrieve all payments from the database with pagination.
        
        Args:
            page (int): The page number for pagination.
            limit (int): The number of records per page.
        
        Returns:
            Dict: A dictionary containing the payment data and total count.
        """
        log_info("Getting all payments")
        try:
            offset = (page - 1) * limit
            query = select(payments_table).offset(offset).limit(limit)
            payments = await database.fetch_all(query)