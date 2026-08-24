import asyncio
from utils.logger_utils import log_info, log_error
from models.payment_outgoing_model import PaymentOutgoing
from repository.payment_outgoing_repository import PaymentOutgoingRepository
from repository.interpayment_repository import InterpaymentRepository
from repository.payment_income_repository import PaymentIncomingRepository
from repository.purchase_repository import PurchaseRepository
from repository.bank_account_repository import BankAccount
from repository.payment_income_repository import PaymentIncomingRepository
from models.mutation_model import Mutation
from typing import List
from utils.errors import internal_error

class CalendarController:

    @staticmethod
    async def tertunda(bankAccounts):
        """
        Pembayaran yang jatuh temponya sudah lewat tetapi belum disetujui.

        Batasnya HARI INI di sisi server, bukan dikirim layar: jam peramban
        dapat meleset atau disetel sendiri, dan daftar yang menuntut tindakan
        tidak boleh bergantung padanya.
        """
        from datetime import date as _d

        data = await PaymentOutgoingRepository.tertunda(_d.today(), bankAccounts)
        return {
            "data": data,
            "count": len(data),
            "total": sum(float(x["amount"] or 0) for x in data),
        }
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
            """
            Keempat kueri dijalankan BERSAMAAN, bukan berurutan.

            Tidak ada yang bergantung pada hasil yang lain — semuanya hanya
            menerima bulan, tahun, dan daftar rekening. Dijalankan
            berurutan, waktu tunggunya adalah JUMLAH keempatnya; bersamaan,
            hanya selama yang paling lambat.

            Aman terhadap kolam koneksi: aiomysql menyediakan sepuluh
            koneksi secara bawaan, sementara yang dipakai di sini empat.
            """
            payments, interpayments, incomes, balances = await asyncio.gather(
                PaymentOutgoingRepository.get_calendar_data(month, year, bankAccounts),
                InterpaymentRepository.get_calendar_data(month, year, bankAccounts),
                PaymentIncomingRepository.get_calendar_data(month, year, bankAccounts),
                Mutation.fetch_by_month_year(month, year, bankAccounts),
            )

            for nama, hasil in (
                ("payments", payments),
                ("interpayments", interpayments),
                ("incomes", incomes),
                ("balances", balances),
            ):
                if isinstance(hasil, dict) and "error" in hasil:
                    log_error(f"Error fetching {nama} calendar data: {hasil['error']}")
                    return {"error": hasil["error"], "status": hasil.get("status", 500)}
            
            return {
                "payments": payments,
                "incomes": incomes,
                "interpayments": interpayments,
                "balances": balances
            }
        except Exception as e:
            log_error(f"Error retrieving calendar data: {str(e)}")
            return internal_error()

    @staticmethod
    async def download_calendar_data(month: int, year: int, bankAccounts: List[int]):
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
            bank_accounts = await BankAccount.get_bank_accounts_by_ids(bankAccounts)
            if "error" in bank_accounts:
                log_error(f"Error fetching bank accounts in calendar data: {bank_accounts['error']}")
                return {"error": bank_accounts["error"], "status": bank_accounts.get("status", 500)}
            
            # Bersamaan, dengan alasan yang sama seperti pada get_calendar_data.
            payments, interpayments, incomes, balances = await asyncio.gather(
                PaymentOutgoingRepository.download_calendar_data(month, year, bankAccounts),
                InterpaymentRepository.get_calendar_data(month, year, bankAccounts),
                PaymentIncomingRepository.get_calendar_data(month, year, bankAccounts),
                Mutation.download_calendar_data(month, year, bankAccounts),
            )

            # Pemeriksaan `balances` sebelumnya keliru membaca `incomes`,
            # sehingga galat pada saldo tidak pernah terdeteksi dan yang
            # dikembalikan adalah pesan milik kueri lain.
            for nama, hasil in (
                ("payments", payments),
                ("interpayments", interpayments),
                ("incomes", incomes),
                ("balances", balances),
            ):
                if isinstance(hasil, dict) and "error" in hasil:
                    log_error(f"Error fetching {nama} calendar data: {hasil['error']}")
                    return {"error": hasil["error"], "status": hasil.get("status", 500)}
            
            return {
                "bank_accounts": bank_accounts,
                "payments": payments,
                "incomes": incomes,
                "interpayments": interpayments,
                "balances": balances
            }
        except Exception as e:
            log_error(f"Error retrieving calendar data: {str(e)}")
            return internal_error()