from typing import Dict, List, Optional
from models.payment_outgoing_model import PaymentOutgoing
from models.dashboard_model import DashboardModel

class DashboardController:
    @staticmethod
    async def fetch_dashboard(dashboardParam, userID: int) -> Dict:
        """
        Fetch dashboard data
        """
        payments = await PaymentOutgoing.fetch_today_payments()

    @staticmethod
    async def cash_position(bank_account_ids: Optional[List[int]] = None) -> Dict:
        """Current cash position per bank account + grand total.

        Returns either the payload dict or {"error": ..., "status": ...},
        following the same convention the route layer already unpacks.
        """
        return await DashboardModel.fetch_cash_position(bank_account_ids)
    