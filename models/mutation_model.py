from pydantic import BaseModel, Field
from datetime import datetime as dt, date as d
from sqlalchemy import Table, Column, Integer, ForeignKey, Float, Date, String, select, func, and_
from utils.database import metadata, database, engine
from utils.logger_utils import log_error
from utils.errors import internal_error

class Mutation(BaseModel):
    bankAccountID: int = Field(..., title="ID of the bank account", ge=1)
    amount: float = Field(..., title="Amount of the mutation")
    date: d = Field(..., title="Date of the mutation")
    type: str = Field(..., title="Purchase type or income type")
    opponent: str = Field(..., title="Opponent of this transaction")
    document: str= Field(...,title="Underlying document")
    balance: float = Field(..., title="Balance of the mutation line")

    @staticmethod
    async def fetch_mutation(bankAccountID: int, page: int, pageSize: int, startDate: d, endDate: d):
        try:
            query = mutation_view.select().where(mutation_view.c.bankaccountid == bankAccountID, mutation_view.c.date >= startDate, mutation_view.c.date <= endDate).limit(pageSize).offset((page - 1) * pageSize)
            result = await database.fetch_all(query)

            count_query = select(func.count()).select_from(mutation_view).where(mutation_view.c.bankaccountid == bankAccountID, mutation_view.c.date >= startDate, mutation_view.c.date <= endDate)
            count = await database.fetch_val(count_query)
            return {"data": result, "count": count if count is not None else 0}
        except Exception as e:
            log_error(f"Error fetching bank accounts: {str(e)}")
            return internal_error()
        
    async def download_mutation(bankAccountID: int, month: int, year: int):
        try:
            query = mutation_view.select().where(mutation_view.c.bankaccountid == bankAccountID, func.extract('month', mutation_view.c.date) == month, func.extract('year', mutation_view.c.date) == year)
            result = await database.fetch_all(query)
            return result
        except Exception as e:
            log_error(f"Error downloading bank account mutation: {str(e)}")
            return internal_error()

    @staticmethod
    async def _saldo_awal(
        month: int, year: int, bank_account_ids: list[int] | None
    ):
        """
        Baris TERAKHIR sebelum tanggal 1 bulan itu, per rekening.

        SATU tempat yang menyusun kueri saldo awal. Layar kalender dan
        unduhannya menyebut angka yang sama, dan sebelumnya masing-masing
        menyusunnya sendiri — dengan hasil yang berbeda, tanpa satu pun dari
        keduanya salah secara mencolok. Yang membacanya menyangka datanya yang
        keliru, bukan kuerinya.

        "Terakhir" tidak cukup ditentukan tanggalnya: beberapa transaksi jatuh
        pada hari yang sama, dan urutannya di dalam hari itu yang menentukan
        saldo mana yang berlaku. Karena itu kuncinya tanggal + `sortorder` +
        `tiebreaker`, disusun sebagai teks berlapis nol supaya urutannya tetap
        benar saat dibandingkan.

        PENYARINGAN REKENING ADA DI DALAM SUBKUERI, bukan ditempelkan di luar.
        Bila disaring di luar, `max_key` tetap dihitung atas SELURUH rekening;
        baris terakhir milik rekening lain lalu tidak berpasangan dengan apa
        pun, dan rekening yang dipilih kehilangan saldo awalnya diam-diam —
        yang tampak sebagai saldo awal yang "belum terpotong".
        """
        from datetime import date

        start_of_month = date(year, month, 1)
        params: dict = {"start_date": start_of_month}

        saring = ""
        if bank_account_ids:
            saring = " AND bankaccountid IN :bank_account_ids"
            params["bank_account_ids"] = tuple(bank_account_ids)

        sql = f"""
        SELECT m.bankaccountid, m.balance
        FROM mutation m
        JOIN (
            SELECT
                bankaccountid,
                MAX(CONCAT(date,'-',LPAD(sortorder,2,'0'),'-',LPAD(tiebreaker,10,'0'))) AS max_key
            FROM mutation
            WHERE date < :start_date{saring}
            GROUP BY bankaccountid
        ) last_row
          ON m.bankaccountid = last_row.bankaccountid
         AND CONCAT(m.date,'-',LPAD(m.sortorder,2,'0'),'-',LPAD(m.tiebreaker,10,'0')) = last_row.max_key
        """
        return await database.fetch_all(sql, params)

    @staticmethod
    async def fetch_by_month_year(month: int, year: int, bank_account_ids: list[int] = None):
        """
        Saldo awal bulan, DIJUMLAHKAN atas rekening yang diminta.

        Dipakai layar yang hanya menampilkan satu angka gabungan.
        """
        try:
            hasil = await Mutation._saldo_awal(month, year, bank_account_ids)
            # Dijumlahkan APA ADANYA, tidak dilewatkan `float`.
            #
            # `balance` berupa DECIMAL; mengubahnya menjadi float lebih dulu
            # menambahkan galat pembulatan pada angka yang dipakai sebagai
            # saldo awal — dan galat itu terbawa ke seluruh baris di bawahnya.
            total = 0
            for r in hasil:
                total += dict(r)["balance"] or 0
            return total
        except Exception as e:
            log_error(f"Error fetching bank account balances: {str(e)}")
            return internal_error()

    @staticmethod
    async def download_calendar_data(month: int, year: int, bank_account_ids: list[int] = None):
        """
        Saldo awal bulan PER REKENING, untuk lembar unduhan.

        Bentuknya berbeda dari `fetch_by_month_year` — baris, bukan satu
        jumlah — tetapi angkanya berasal dari kueri yang sama persis.

        Sebelumnya kueri di sini disusun terpisah, dan penyaring rekeningnya
        memakai penanda `%s` bergaya driver lain sementara nilainya dikirim
        sebagai parameter bernama `acc_0`, `acc_1`, ... — penanda yang tidak
        pernah terisi. Penyaringnya pun ditempelkan SESUDAH klausa ON,
        sehingga ia menjadi bagian dari syarat JOIN dan subkuerinya tetap
        menghitung seluruh rekening.
        """
        try:
            return await Mutation._saldo_awal(month, year, bank_account_ids)
        except Exception as e:
            log_error(f"Error fetching bank account balances: {str(e)}")
            return internal_error()

mutation_view = Table(
    "mutation",
    metadata,
    autoload_with=engine,
)