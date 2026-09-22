from repository.kalender_terjadwal_repository import KalenderTerjadwalRepository
import asyncio
from datetime import date, timedelta
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
    async def terjadwal(mulai, akhir, bankAccounts):
        """
        Pembayaran tertunda sebelum `mulai` (per rekening) dan pembayaran
        terjadwal per tanggal di [mulai, akhir] — lihat
        `KalenderTerjadwalRepository`. `akhir` boleh kosong: hanya bawaan.
        """
        try:
            bawaan = await KalenderTerjadwalRepository.bawaan(mulai, bankAccounts)
            harian = (
                await KalenderTerjadwalRepository.harian(mulai, akhir, bankAccounts)
                if akhir
                else []
            )
            return {
                "bawaan": bawaan,
                "bawaanKeluar": round(sum(b["keluar"] for b in bawaan), 2),
                "bawaanMasuk": round(sum(b["masuk"] for b in bawaan), 2),
                "bawaanJumlah": sum(b["jumlah"] for b in bawaan),
                "harian": harian,
            }
        except Exception as e:  # noqa: BLE001
            log_error(f"Kalender terjadwal gagal: {e}")
            return {"error": "Internal server error.", "status": 500}

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

    # Batas rentang unduhan, dalam hari.
    #
    # Bukan angka yang dipilih asal: berkasnya dirakit di PERAMBAN — seluruh
    # transaksi rentang itu dikirim utuh, lalu disusun menjadi kisi kalender
    # per rekening per bulan. Rentang setahun pada perusahaan yang ramai
    # membuat tab-nya diam beberapa menit tanpa satu pun pesan galat, dan
    # yang menunggunya akan menutupnya lebih dulu.
    #
    # Ditegakkan DI SINI, bukan hanya di dialognya. Batas yang cuma ada di
    # layar bukan batas — `?start=2020-01-01&end=2026-12-31` melewatinya
    # tanpa menyentuh dialog sama sekali.
    MAKS_HARI_RENTANG = 60

    @staticmethod
    async def download_calendar_rentang(
        mulai: date, akhir: date, bankAccounts: List[int]
    ):
        """
        Data kalender untuk RENTANG TANGGAL, `akhir` termasuk.

        Bedanya dengan versi bulan bukan cuma penyaring tanggalnya. SALDO
        AWAL-nya pun berbeda: titik nolnya baris terakhir sebelum `mulai`,
        bukan sebelum tanggal 1 bulan. Memakai saldo awal bulan untuk
        rentang yang mulai di tengah bulan menggeser SELURUH garis saldonya
        sebanyak mutasi yang sudah terjadi bulan itu — dan garis yang
        bergeser rata tetap terlihat masuk akal.
        """
        if akhir < mulai:
            return {
                "error": "Tanggal akhir tidak boleh mendahului tanggal mulai.",
                "status": 400,
            }

        jumlah_hari = (akhir - mulai).days + 1
        if jumlah_hari > CalendarController.MAKS_HARI_RENTANG:
            return {
                "error": (
                    f"Rentang paling banyak {CalendarController.MAKS_HARI_RENTANG} "
                    f"hari; yang diminta {jumlah_hari} hari."
                ),
                "status": 400,
            }

        # Batas atas dijadikan EKSKLUSIF sekali di sini, supaya tidak ada
        # repository yang harus menebak apakah `akhir` termasuk atau tidak.
        akhir_eks = akhir + timedelta(days=1)

        log_info(
            f"Retrieving calendar data between {mulai} and {akhir} "
            f"({jumlah_hari} hari)"
        )

        try:
            bank_accounts = await BankAccount.get_bank_accounts_by_ids(bankAccounts)
            if "error" in bank_accounts:
                log_error(f"Error fetching bank accounts in calendar data: {bank_accounts['error']}")
                return {"error": bank_accounts["error"], "status": bank_accounts.get("status", 500)}

            payments, interpayments, incomes, balances = await asyncio.gather(
                PaymentOutgoingRepository.download_calendar_rentang(mulai, akhir_eks, bankAccounts),
                InterpaymentRepository.get_calendar_rentang(mulai, akhir_eks, bankAccounts),
                PaymentIncomingRepository.get_calendar_rentang(mulai, akhir_eks, bankAccounts),
                Mutation.download_calendar_rentang(mulai, bankAccounts),
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
                "bank_accounts": bank_accounts,
                "payments": payments,
                "incomes": incomes,
                "interpayments": interpayments,
                "balances": balances,
                # Rentangnya IKUT DIKEMBALIKAN, dan bukan hiasan: yang
                # merakit berkasnya menyusun barisnya dari rentang ini, dan
                # kalau ia memakai tanggal yang dikirimnya sendiri, ia tidak
                # akan pernah tahu server memotongnya.
                "start": mulai.isoformat(),
                "end": akhir.isoformat(),
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
            
            # Rentang bulannya disebutkan dalam bentuk yang SAMA dengan
            # jawaban per rentang, supaya yang merakit berkasnya punya satu
            # jalur saja. Dua bentuk jawaban berarti dua jalur perakitan, dan
            # yang satu akan tertinggal saat yang lain diperbaiki.
            akhir_bulan = (
                date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            ) - timedelta(days=1)

            return {
                "bank_accounts": bank_accounts,
                "payments": payments,
                "incomes": incomes,
                "interpayments": interpayments,
                "balances": balances,
                "start": date(year, month, 1).isoformat(),
                "end": akhir_bulan.isoformat(),
            }
        except Exception as e:
            log_error(f"Error retrieving calendar data: {str(e)}")
            return internal_error()