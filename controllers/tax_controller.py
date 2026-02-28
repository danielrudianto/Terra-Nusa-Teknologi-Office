from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from repository.purchase_repository import PurchaseRepository
from models.payment_outgoing_model import PaymentOutgoing
from repository.salary_slip_repository import SalarySlipRepository
from repository.sales_invoice_repository import SalesInvoiceRepository
from repository.mutation_repository import MutationRepository
from repository.asset_repository import AssetRepository
from repository.loan_repository import LoanRepository
from repository.bank_account_repository import BankAccount

class TaxController:
    @staticmethod
    async def get_ppn_report(month: int, year: int):
        try:
            result = await PurchaseRepository.get_ppn_report(month, year)
            if "error" in result:
                log_error(f"Error fetching PPN report: {result['error']}")
                return {"error": result["error"], "status": result["status"]}
            
            return result
        except Exception as e:
            log_error(f"Error fetching purchase PPN: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_pph_report(month: int, year: int):
        log_info(f"Fetching PPh report for month {month} and year {year}")
        try:
            purchases = await PaymentOutgoing.get_purchase_pph_report(month, year)
            if "error" in purchases:
                log_error(f"Error fetching purchase data: {purchases['error']}")
                raise HTTPException(status_code=purchases.get("status", 500), detail=purchases["error"])
            
            expenses = await PaymentOutgoing.get_expense_pph_report(month, year)
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