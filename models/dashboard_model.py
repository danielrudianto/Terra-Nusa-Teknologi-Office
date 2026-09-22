from datetime import date, timedelta
from typing import Optional, List

from utils.database import database
from utils.logger_utils import log_error
from utils.errors import internal_error


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
                "SELECT id, bankName, bankAccountName, bankAccountNumber, "
                "excludeFromCalendar "
                "FROM bank_accounts "
                "WHERE isDelete = 0"
                + DashboardModel._account_filter(bank_account_ids, "id")
                + " ORDER BY id"
            )
            accounts = await database.fetch_all(account_sql)

            # Daftar rekening yang DISEBUT pemanggil menang atas tanda
            # `excludeFromCalendar`.
            #
            # Tandanya adalah PILIHAN AWAL, bukan larangan: pemilih rekening di
            # kalender mencentangnya dengan `!excludeFromCalendar`, dan yang
            # membukanya tetap boleh mencentang rekening yang dikecualikan.
            # Bila tanda itu tetap menyaring sesudah rekeningnya diminta
            # dengan nama, yang memintanya akan menerima NOL tanpa penjelasan —
            # dan angka nol yang salah tidak pernah terlihat salah.
            #
            # Jadi: tanpa daftar (beranda) tandanya berlaku; dengan daftar,
            # yang diminta itulah yang dihitung.
            hormati_tanda = not bank_account_ids

            data = []
            total = 0.0
            total_dikecualikan = 0.0
            jumlah_dikecualikan = 0
            for a in accounts:
                mut = balance_by_id.get(a["id"])
                bal = float(mut["balance"]) if mut and mut["balance"] is not None else 0.0
                dikecualikan = bool(
                    hormati_tanda and getattr(a, "excludeFromCalendar", False)
                )
                if dikecualikan:
                    total_dikecualikan += bal
                    jumlah_dikecualikan += 1
                else:
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
                    "excludeFromCalendar": dikecualikan,
                })

            return {
                "accounts": data,
                # `totalBalance` TIDAK memuat rekening yang dikecualikan.
                #
                # Namanya sengaja tidak diubah: `proyeksi-kas` membacanya
                # sebagai titik jangkar proyeksi, dan ia selalu mengirim daftar
                # rekening, sehingga angkanya di sana tidak bergeser sama
                # sekali oleh perubahan ini.
                "totalBalance": total,
                # Yang dikecualikan tetap DILAPORKAN, tidak dihilangkan.
                #
                # Uang di rekening jaminan tetap uang. Membuangnya dari
                # jawaban berarti satu-satunya layar yang menyebut saldo
                # rekening berhenti menyebutnya — dan saldo yang tidak pernah
                # ditampilkan adalah saldo yang tidak pernah dicocokkan.
                "excludedBalance": total_dikecualikan,
                "excludedCount": jumlah_dikecualikan,
                "grandTotalBalance": total + total_dikecualikan,
                "accountCount": len(data),
                "generatedAt": today.isoformat(),
            }
        except Exception as e:
            # Matches the app convention: if the `mutation` view is missing the
            # balance query fails -- surface it rather than returning wrong zeros.
            log_error(f"Error fetching cash position (mutation view may not exist): {str(e)}")
            return internal_error()

    @staticmethod
    async def fetch_cash_trend(days: int = 30) -> dict:
        """Total saldo kas per HARI selama `days` hari terakhir (termasuk hari ini).

        Aturan cakupannya SAMA dengan `totalBalance` di `fetch_cash_position`
        tanpa daftar rekening: rekening aktif, rekening `excludeFromCalendar`
        tidak dihitung. Titik terakhir deret ini karenanya sama persis dengan
        Total Saldo yang tertulis besar di atasnya — dua angka di kartu yang
        sama tidak boleh berselisih.

        Saldo sebuah hari = saldo berjalan baris mutasi TERAKHIR pada atau
        sebelum hari itu (urutan tanggal, sortorder, tiebreaker — sama dengan
        kueri posisi kas). Hari tanpa mutasi mewarisi saldo hari sebelumnya.
        """
        try:
            days = max(2, min(int(days or 30), 120))
            today = date.today()
            mulai = today - timedelta(days=days - 1)

            akun = await database.fetch_all(
                "SELECT id FROM bank_accounts "
                "WHERE isDelete = 0 AND (excludeFromCalendar = 0 OR excludeFromCalendar IS NULL)"
            )
            ids = [int(a["id"]) for a in akun]
            if not ids:
                return {"hari": days, "titik": [
                    {"tanggal": (mulai + timedelta(days=i)).isoformat(), "saldo": 0.0}
                    for i in range(days)
                ]}
            daftar = ",".join(str(i) for i in ids)

            # Saldo akhir tiap rekening SEBELUM jendela dimulai.
            dasar = await database.fetch_all(f"""
                SELECT m.bankaccountid AS id, m.balance AS saldo
                FROM mutation m
                JOIN (
                    SELECT bankaccountid,
                           MAX(CONCAT(date, '-', LPAD(sortorder, 2, '0'), '-',
                                      LPAD(tiebreaker, 10, '0'))) AS max_key
                    FROM mutation
                    WHERE date < :mulai AND bankaccountid IN ({daftar})
                    GROUP BY bankaccountid
                ) t ON m.bankaccountid = t.bankaccountid
                   AND CONCAT(m.date, '-', LPAD(m.sortorder, 2, '0'), '-',
                              LPAD(m.tiebreaker, 10, '0')) = t.max_key
            """, {"mulai": mulai})

            dalam = await database.fetch_all(f"""
                SELECT bankaccountid AS id, date AS tanggal, balance AS saldo
                FROM mutation
                WHERE date >= :mulai AND date <= :hari_ini
                  AND bankaccountid IN ({daftar})
                ORDER BY date, sortorder, tiebreaker
            """, {"mulai": mulai, "hari_ini": today})

            return {"hari": days, "titik": susun_tren(
                ids,
                {int(r["id"]): float(r["saldo"] or 0) for r in dasar},
                [(int(r["id"]), r["tanggal"], float(r["saldo"] or 0)) for r in dalam],
                mulai,
                days,
            )}
        except Exception as e:
            log_error(f"Error fetching cash trend: {str(e)}")
            return internal_error()


def susun_tren(ids, dasar: dict, baris: list, mulai: date, days: int) -> list:
    """Deret harian dari saldo awal + baris mutasi yang SUDAH berurutan.

    Dipisah dari kueri supaya aturannya dapat diuji tanpa basis data:
    baris terakhir pada suatu hari menang, dan hari kosong mewarisi saldo.
    """
    saldo = {i: dasar.get(i, 0.0) for i in ids}
    per_hari: dict = {}
    for akun, tgl, nilai in baris:
        per_hari.setdefault(tgl, []).append((akun, nilai))
    titik = []
    for i in range(days):
        hari = mulai + timedelta(days=i)
        for akun, nilai in per_hari.get(hari, []):
            saldo[akun] = nilai
        titik.append({"tanggal": hari.isoformat(), "saldo": round(sum(saldo.values()), 2)})
    return titik

