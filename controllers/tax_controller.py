from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from repository.purchase_repository import PurchaseRepository
from models.payment_outgoing_model import PaymentOutgoing
from repository.payment_outgoing_repository import PaymentOutgoingRepository
from repository.salary_slip_repository import SalarySlipRepository
from repository.sales_invoice_repository import SalesInvoiceRepository
from repository.mutation_repository import MutationRepository
from repository.asset_repository import AssetRepository
from repository.loan_repository import LoanRepository
from repository.bank_account_repository import BankAccount
from repository.expense_repository import ExpenseRepository
from utils.errors import internal_error

class TaxController:
    @staticmethod
    async def get_ppn_report(month: int, year: int):
        """
        PPN masukan dari DUA sumber: pembelian dan beban.

        Sebelumnya hanya pembelian. Setelah beban dapat mencatat PPN, rekap
        yang membaca satu tabel saja membuat PPN masukan dari beban tercatat
        tetapi tidak pernah terhitung — keadaan yang lebih berbahaya daripada
        tidak mencatatnya sama sekali, karena orang mengira sudah masuk.

        Kosongnya salah satu sumber BUKAN galat. Sebelumnya pembelian tanpa
        PPN mengembalikan 404, dan itu ikut menggagalkan seluruh rekap meski
        bebannya ada. Yang dianggap galat hanya kegagalan kueri.
        """
        try:
            dari_pembelian = await PurchaseRepository.get_ppn_report(month, year)
            dari_beban = await ExpenseRepository.get_ppn_report(month, year)

            def bersih(hasil, nama):
                """Kosong dianggap tidak ada baris; hanya galat kueri yang dilaporkan."""
                if isinstance(hasil, dict):
                    if hasil.get("status") == 404:
                        return []
                    log_error(f"Error fetching PPN from {nama}: {hasil.get('error')}")
                    raise RuntimeError(hasil.get("error"))
                return hasil or []

            baris = bersih(dari_pembelian, "purchases")
            # Penanda asal ditambahkan di sini agar baris pembelian lama
            # yang belum punya kolomnya tetap ikut tertandai.
            for b in baris:
                b.setdefault("sumber", "purchase")
            baris += bersih(dari_beban, "expenses")

            if not baris:
                return {
                    "error": "No PPN records found for this period",
                    "status": 404,
                }

            # Diurutkan ulang: dua sumber digabung, urutannya menjadi acak
            # bila tidak disusun kembali menurut tanggalnya.
            baris.sort(key=lambda x: (x.get("date") is None, x.get("date")))
            return baris
        except RuntimeError as e:
            return internal_error()
        except Exception as e:
            log_error(f"Error fetching PPN report: {str(e)}")
            return internal_error()
        
    @staticmethod
    async def get_ppn_position(month: int, year: int):
        """
        Posisi PPN satu periode: estimasi kurang/lebih bayar.

        PPN keluaran (dari faktur penjualan) dikurangi PPN masukan yang DAPAT
        dikreditkan (pembelian/beban yang sudah punya nomor faktur pajak).
        Masukan tanpa faktur pajak dipisah — nilainya nyata tetapi belum boleh
        mengurangi setoran sampai fakturnya terbit, jadi tidak ikut dalam
        selisih melainkan ditampilkan sebagai catatan.

        Selisih positif berarti kurang bayar (harus disetor), negatif berarti
        lebih bayar (kelebihan/kredit). Angka ini ESTIMASI: bergantung pada
        kelengkapan faktur pajak yang sudah tercatat pada saat laporan dibuka.
        """
        try:
            # --- Keluaran: faktur penjualan ber-PPN ---
            keluaran_rows = await SalesInvoiceRepository.get_ppn_keluaran(
                month, year
            )
            if isinstance(keluaran_rows, dict) and keluaran_rows.get("error"):
                log_error(
                    f"Error fetching PPN keluaran: {keluaran_rows.get('error')}"
                )
                return internal_error()

            # --- Masukan: pembelian + beban ber-PPN ---
            dari_pembelian = await PurchaseRepository.get_ppn_report(month, year)
            dari_beban = await ExpenseRepository.get_ppn_report(month, year)

            def bersih(hasil, nama):
                """Kosong bukan galat; hanya kegagalan kueri yang dilaporkan."""
                if isinstance(hasil, dict):
                    if hasil.get("status") == 404:
                        return []
                    log_error(f"Error fetching PPN from {nama}: {hasil.get('error')}")
                    raise RuntimeError(hasil.get("error"))
                return hasil or []

            masukan_rows = bersih(dari_pembelian, "purchases")
            for b in masukan_rows:
                b.setdefault("sumber", "purchase")
            masukan_rows += bersih(dari_beban, "expenses")

            def nilai_ppn(row):
                """PPN = DPP × persen / 100. `ppn` selalu tersimpan sebagai persen."""
                dpp = row.get("dpp") or 0
                ppn = row.get("ppn") or 0
                return (dpp * ppn) / 100

            def ada_faktur(row):
                return bool((row.get("taxInvoiceName") or "").strip())

            # Keluaran
            for r in keluaran_rows:
                r["ppnValue"] = nilai_ppn(r)
            keluaran_total = sum(nilai_ppn(r) for r in keluaran_rows)

            # Masukan dibagi dua: yang sudah ada faktur (dapat dikreditkan) dan
            # yang belum (nyata, tetapi belum boleh mengurangi setoran).
            kreditable, tanpa_faktur = [], []
            for r in masukan_rows:
                r["ppnValue"] = nilai_ppn(r)
                (kreditable if ada_faktur(r) else tanpa_faktur).append(r)

            kreditable_total = sum(nilai_ppn(r) for r in kreditable)
            tanpa_faktur_total = sum(nilai_ppn(r) for r in tanpa_faktur)

            selisih = keluaran_total - kreditable_total
            if selisih > 5:
                status = "kurang_bayar"
            elif selisih < -5:
                status = "lebih_bayar"
            else:
                status = "nihil"

            # Diurutkan menurut tanggal agar rincian mudah ditelusuri.
            def urut(rows):
                rows.sort(key=lambda x: (x.get("date") is None, x.get("date")))
                return rows

            return {
                "month": month,
                "year": year,
                "status": status,
                "keluaran": {
                    "total": keluaran_total,
                    "rows": urut(keluaran_rows),
                },
                "masukanKreditable": {
                    "total": kreditable_total,
                    "rows": urut(kreditable),
                },
                "masukanTanpaFaktur": {
                    "total": tanpa_faktur_total,
                    "rows": urut(tanpa_faktur),
                },
                # Selisih = keluaran − masukan yang dapat dikreditkan.
                "selisih": selisih,
                # Bila semua faktur masukan terbit, selisihnya menjadi ini.
                "selisihBilaLengkap": keluaran_total
                - kreditable_total
                - tanpa_faktur_total,
            }
        except RuntimeError:
            return internal_error()
        except Exception as e:
            log_error(f"Error fetching PPN position: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_pph_report(month: int, year: int):
        log_info(f"Fetching PPh report for month {month} and year {year}")
        try:
            purchases = await PaymentOutgoingRepository.get_purchase_pph_report(month, year)
            if "error" in purchases:
                log_error(f"Error fetching purchase data: {purchases['error']}")
                raise HTTPException(status_code=purchases.get("status", 500), detail=purchases["error"])
            
            expenses = await PaymentOutgoingRepository.get_expense_pph_report(month, year)
            if "error" in expenses:
                log_error(f"Error fetching expense data: {expenses['error']}")
                raise HTTPException(status_code=expenses.get("status", 500), detail=expenses["error"])
            
            return {
                "purchase": purchases,
                "expense": expenses
            }
        except IntegrityError as e:
            log_error(f"Integrity error: {str(e)}")
            raise HTTPException(status_code=400, detail="Asset already exists.")
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")
        
    @staticmethod
    async def get_pph_salary_report(month: int, year: int):
        log_info(f"Fetching PPh report for month {month} and year {year}")
        try:
            salary_slip = await SalarySlipRepository.get_pph_report(month, year)
            if "error" in salary_slip:
                log_error(f"Error fetching salary slip data: {salary_slip['error']}")
                raise HTTPException(status_code=salary_slip.get("status", 500), detail=salary_slip["error"])
            
            return salary_slip
        except IntegrityError as e:
            log_error(f"Integrity error: {str(e)}")
            raise HTTPException(status_code=400, detail="Asset already exists.")
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def get_monthly_recap(params: dict):
        month = params.get("month")
        year = params.get("year")
        mutation = params.get("mutation")
        purchase = params.get("purchase")
        sales = params.get("sales")
        loans = params.get("loans")
        asset = params.get("asset")
        ar = params.get("ar")
        ap = params.get("ap")

        log_info(f"Fetching monthly recap for month {month} and year {year}")
        log_info(f"Fetching report with parameters of mutation: {mutation}, purchase: {purchase}, sales: {sales}, loans: {loans}, asset: {asset}, ar: {ar}, ap: {ap}")

        try:
            response = {}

            if sales:
                salesData = await SalesInvoiceRepository.get_monthly_recap(month, year)
                if "error" in salesData:
                    log_error(f"Error fetching sales data: {salesData['error']}")
                    raise HTTPException(status_code=salesData.get("status", 500), detail=salesData["error"])
                response["sales"] = salesData

            if purchase:
                purchaseData = await PurchaseRepository.get_monthly_recap(month, year)
                if "error" in purchaseData:
                    log_error(f"Error fetching purchase data: {purchaseData['error']}")
                    raise HTTPException(status_code=purchaseData.get("status", 500), detail=purchaseData["error"])
                response["purchase"] = purchaseData

            if mutation:
                mutationData = await MutationRepository.get_monthly_mutation(month, year)

                if "error" in mutationData:
                    log_error(f"Error fetching mutation data: {mutationData['error']}")
                    raise HTTPException(
                        status_code=mutationData.get("status", 500),
                        detail=mutationData["error"]
                    )

                # ambil bank id yg punya data
                valid_bank_ids = [
                    key for key, value in mutationData.items()
                    if value.get("data")
                ]

                if valid_bank_ids:
                    bankDetails = await BankAccount.get_bank_accounts_by_ids(valid_bank_ids)
                    bank_map = { bank.id: bank for bank in bankDetails }
                else:
                    bank_map = {}

                # inject detail
                for key, mutation in mutationData.items():
                    mutation["detail"] = bank_map.get(key)

                response["mutation"] = mutationData

            if ar:
                arData = await SalesInvoiceRepository.get_monthly_ar(month, year)
                if "error" in arData:
                    log_error(f"Error fetching AR data: {arData['error']}")
                    raise HTTPException(status_code=arData.get("status", 500), detail=arData["error"])
                response["ar"] = arData

            if ap:
                apData = await PurchaseRepository.get_monthly_ap(month, year)
                if "error" in apData:
                    log_error(f"Error fetching AP data: {apData['error']}")
                    raise HTTPException(status_code=apData.get("status", 500), detail=apData["error"])
                response["ap"] = apData

            if asset:
                assetData = await AssetRepository.get_monthly_asset(month, year)
                if "error" in assetData:
                    log_error(f"Error fetching asset data: {assetData['error']}")
                    raise HTTPException(status_code=assetData.get("status", 500), detail=assetData["error"])
                response["asset"] = assetData
                
            if loans:
                loansData = await LoanRepository.get_monthly_loan(month, year)
                if "error" in loansData:
                    log_error(f"Error fetching loan data: {loansData['error']}")
                    raise HTTPException(status_code=loansData.get("status", 500), detail=loansData["error"])
                response["loans"] = loansData

            return response
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")