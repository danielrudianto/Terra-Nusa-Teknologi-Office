# repositories/mutation_repository.py

from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy import select, and_
from utils.database import database
from utils.logger_utils import log_error
from models.mutation_model import mutation_view
from collections import defaultdict


class MutationRepository:
    @staticmethod
    async def get_monthly_mutation(
        month: int, year: int
    ) -> Dict[str, Any]:
        """
        Get mutation per month grouped by bankAccountID
        """

        try:
            start_date = datetime(year, month, 1)

            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)

            query = (
                select(mutation_view)
                .where(
                    and_(
                        mutation_view.c.date >= start_date,
                        mutation_view.c.date < end_date
                    )
                )
                .order_by(
                    mutation_view.c.bankaccountid.asc(),
                    mutation_view.c.date.asc()
                )
            )

            result = await database.fetch_all(query)

            grouped_data = defaultdict(list)

            for row in result:
                row_dict = dict(row)
                bank_id = row_dict["bankaccountid"]
                grouped_data[bank_id].append(row_dict)

            # Optional: tambahin count per rekening
            final_result = {
                bank_id: {
                    "data": rows,
                    "count": len(rows)
                }
                for bank_id, rows in grouped_data.items()
            }

            return final_result

        except Exception as e:
            log_error(f"Error fetching monthly mutation: {str(e)}")
            return {"error": "Internal server error.", "status": 500}