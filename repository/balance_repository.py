from typing import List, Optional, Dict, Any
from sqlalchemy import select, func
from utils.database import metadata, database
from utils.logger_utils import log_error
from models.balance_model import BalanceResponse, balance_view

class BalanceRepository:
    @staticmethod
    async def fetch_by_bank_account_ids(account_ids: List[int]) -> List[BalanceResponse]:
        """
        Fetch balances for multiple bank account IDs.
        
        Args:
            account_ids: List of bank account IDs
            
        Returns:
            List of BalanceResponse objects
        """
        try:
            if not account_ids:
                return []

            query = balance_view.select().where(balance_view.c.id.in_(account_ids))
            result = await database.fetch_all(query)

            return [BalanceResponse.model_validate(dict(row)) for row in result]
            
        except Exception as e:
            log_error(f"Error fetching bank account balances: {str(e)}")
            raise

    @staticmethod
    async def fetch_by_bank_account_id(account_id: int) -> Optional[BalanceResponse]:
        """
        Fetch balance for a single bank account ID.
        
        Args:
            account_id: Bank account ID
            
        Returns:
            BalanceResponse object or None if not found
        """
        try:
            query = balance_view.select().where(balance_view.c.id == account_id)
            result = await database.fetch_one(query)
            
            return BalanceResponse.model_validate(dict(result)) if result else None
            
        except Exception as e:
            log_error(f"Error fetching bank account balance for ID {account_id}: {str(e)}")
            raise

    @staticmethod
    async def fetch_all_balances() -> List[BalanceResponse]:
        """
        Fetch balances for all bank accounts.
        
        Returns:
            List of BalanceResponse objects
        """
        try:
            query = balance_view.select()
            result = await database.fetch_all(query)
            
            return [BalanceResponse.model_validate(dict(row)) for row in result]
            
        except Exception as e:
            log_error(f"Error fetching all bank account balances: {str(e)}")
            raise

    @staticmethod
    async def get_total_balance() -> float:
        """
        Get the total balance across all bank accounts.
        
        Returns:
            Total balance as float
        """
        try:
            query = select(func.sum(balance_view.c.balance)).select_from(balance_view)
            result = await database.fetch_val(query)
            
            return result or 0.0
            
        except Exception as e:
            log_error(f"Error calculating total balance: {str(e)}")
            raise

    @staticmethod
    async def get_balances_with_pagination(
        page: int = 1, 
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        Get paginated balances.
        
        Args:
            page: Page number (starting from 1)
            page_size: Number of items per page
            
        Returns:
            Dictionary with balances and pagination info
        """
        try:
            # Calculate offset
            offset = (page - 1) * page_size
            
            # Get paginated results
            query = balance_view.select().limit(page_size).offset(offset)
            result = await database.fetch_all(query)
            balances = [BalanceResponse.model_validate(dict(row)) for row in result]
            
            # Get total count
            count_query = select(func.count()).select_from(balance_view)
            total_count = await database.fetch_val(count_query)
            
            return {
                "data": balances,
                "count": len(balances),
                "total_count": total_count or 0,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_count + page_size - 1) // page_size if total_count else 0
            }
            
        except Exception as e:
            log_error(f"Error fetching paginated balances: {str(e)}")
            raise