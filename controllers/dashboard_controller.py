from typing import Dict, List, Optional
from models.payment_outgoing_model import PaymentOutgoing

class DashboardController:
    @staticmethod
    async def fetch_dashboard(dashboardParam, userID: int) -> Dict:
        """
        Fetch dashboard data
        """
        payments = await PaymentOutgoing.fetch_today_payments()