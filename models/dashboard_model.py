from datetime import date
from typing import Optional, List

from utils.database import database
from utils.logger_utils import log_error


class DashboardModel:
    """Read-only aggregations for dashboard widgets.

    Cash position is derived from the `mutation` MySQL view, which stores a
    running `balance` per row per bank account. The latest row (as of today)
    for each account IS that account's current real balance -- so we never
    assume a zero opening balance.
    """

    @staticmethod
    def _account_filter(bank_account_ids: Optional[List[int]], column: str) -> str:
        """Build a safe `AND col IN (...)` clause from a list of ints.

        Values are cast to int, so there is no injection surface even though
        they are inlined (the `databases`/aiomysql driver does not expand a
        tuple bound to `IN :param` reliably).
        """
        if not bank_account_ids:
            return ""
        ids = ",".join(str(int(x)) for x in bank_account_ids)
        return f" AND {column} IN ({ids})"

    @staticmethod
    async def fetch_cash_position(bank_account_ids: Optional[List[int]] = None) -> dict:
        try:
            today = date.today()

            # 1) Latest mutation row per account, as of today.
            #    Ignore future-dated rows so scheduled/unposted entries don't
            #    inflate the current balance. The CONCAT(date, sortorder,
            #    tiebreaker) key mirrors the ordering used elsewhere in the app.
            mutation_sql = f"""
                SELECT m.bankaccountid AS bankAccountID,
                       m.balance       AS balance,
                       m.date          AS lastMutationDate
                FROM mutation m
                JOIN (
                    SELECT bankaccountid,
                           MAX(CONCAT(date, '-',
                                      LPAD(sortorder, 2, '0'), '-',
                                      LPAD(tiebreaker, 10, '0'))) AS max_key
                    FROM mutation
                    WHERE date <= :today{DashboardModel._account_filter(bank_account_ids, "bankaccountid")}
                    GROUP BY bankaccountid
                ) last_row
                  ON m.bankaccountid = last_row.bankaccountid
                 AND CONCAT(m.date, '-',
                            LPAD(m.sortorder, 2, '0'), '-',
                            LPAD(m.tiebreaker, 10, '0')) = last_row.max_key
            """
            mutation_rows = await database.fetch_all(mutation_sql, {"today": today})
            balance_by_id = {r["bankAccountID"]: r for r in mutation_rows}

            # 2) All active bank accounts (so accounts with no mutations still
            #    show up, at balance 0, instead of silently disappearing).
            account_sql = (
                "SELECT id, bankName, bankAccountName, bankAccountNumber "
                "FROM bank_accounts "
                "WHERE isDelete = 0"
                + DashboardModel._account_filter(bank_account_ids, "id")
                + " ORDER BY id"
            )
            accounts = await database.fetch_all(account_sql)

            data = []
            total = 0.0
            for a in accounts:
                mut = balance_by_id.get(a["id"])
                bal = float(mut["balance"]) if mut and mut["balance"] is not None else 0.0
                total += bal
                data.append({
                    "bankAccountID": a["id"],
                    "bankName": a["bankName"],
                    "bankAccountName": a["bankAccountName"],
                    "bankAccountNumber": a["bankAccountNumber"],
                    "balance": bal,
                    "lastMutationDate": (
                        mut["lastMutationDate"].isoformat()
                        if mut and mut["lastMutationDate"] else None
                    ),
                    "hasActivity": mut is not None,
                })

            return {
                "accounts": data,
                "totalBalance": total,
                "accountCount": len(data),
                "generatedAt": today.isoformat(),
            }
        except Exception as e:
            # Matches the app convention: if the `mutation` view is missing the
            # balance query fails -- surface it rather than returning wrong zeros.
            log_error(f"Error fetching cash position (mutation view may not exist): {str(e)}")
            return {"error": str(e), "status": 500}