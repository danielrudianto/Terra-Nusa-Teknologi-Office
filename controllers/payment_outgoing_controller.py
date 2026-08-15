import asyncio
from utils.errors import ErrorCode, app_error, internal_error
from sqlalchemy import func, insert, select, update, delete, or_
from utils.database import database
from models.payment_outgoing_model import PaymentOutgoing
from repository.payment_outgoing_repository import PaymentOutgoingRepository
from repository.purchase_repository import PurchaseRepository
from repository.reimbursement_repository import ReimbursementRepository
from repository.salary_slip_repository import SalarySlipRepository, SalarySlipAllowanceRepository, SalarySlipDeductionRepository
from repository.expense_repository import ExpenseRepository
from repository.bank_account_repository import BankAccount
from models.balance_model import Balance
from repository.interpayment_repository import InterpaymentRepository
from repository.loan_repository import LoanRepository
from utils.logger_utils import log_error, log_info

# Fee charged per transfer to an account at a different bank (IDR).
INTERBANK_TRANSFER_FEE = 2500
from datetime import datetime as dt, date as d
from fastapi import HTTPException
from typing import List
from functools import reduce
from datetime import date


def add(x, y):
    return x + y.amount

class PaymentOutgoingController:
    @staticmethod
    async def create_payment(payment_data: dict, userID: int):
        """
        Create a new payment in the database.
        
        Args:
            payment_data (dict): The data of the payment to create.
            userID (int): The ID of the user creating the payment.
        
        Returns:
            dict: A success message with the created payment ID.
        """
        payment_data["createdBy"] = userID
        payment_data["createdAt"] = dt.now()
        log_info(f"Creating payment with data: {payment_data}")
        
        try:
            result = await PaymentOutgoingRepository.create(payment_data)
            if "error" in result:
                log_error(f"Error creating payment: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error creating payment: {str(e)}")
            return internal_error()
        
    @staticmethod
    async def get_payments_by_purchase_id(purchase_id: int):
        """
        Get payments by purchase ID.
        
        Args:
            purchase_id (int): The ID of the purchase.
        
        Returns:
            list: A list of payments for the specified purchase.
        """
        log_info(f"Retrieving payments for purchase ID: {purchase_id}")
        
        try:
            payments = await PaymentOutgoingRepository.get_payments_by_purchase_id(purchase_id)
            if "error" in payments:
                log_error(f"Error fetching payments for purchase ID {purchase_id}: {payments['error']}")
                return {"error": payments["error"], "status": payments.get("status", 500)}
            
            log_info(f"Retrieved {len(payments)} payments for purchase ID: {purchase_id}")
            return {"payments": payments}
        except Exception as e:
            log_error(f"Error retrieving payments: {str(e)}")
            return internal_error()
    
    @staticmethod
    async def get_payment_by_id(id: int):
        """
        Get a payment by ID.
        
        Args:
            id (int): The ID of the payment.
        
        Returns:
            dict: The payment details or an error message if not found.
        """
        log_info(f"Retrieving payment with ID: {id}")
        
        try:
            payment = await PaymentOutgoingRepository.get_payment_by_id(id)
            if "error" in payment:
                log_error(f"Error fetching payment with ID {id}: {payment['error']}")
                return {"error": payment["error"], "status": payment.get("status")}
            log_info(f"Payment with ID: {id} retrieved successfully")
            
            bankAccountID = payment.bankAccountID
            bankAccount = await BankAccount.get_bank_account_by_id(bankAccountID)
            if "error" in bankAccount:
                log_error(f"Error fetching bank account with ID {bankAccountID}: {bankAccount['error']}")
                return {"error": bankAccount["error"], "status": bankAccount.get("status")}
            
            purchase = None
            reimbursement = None
            expense = None
            salarySlip = None

            if payment.reimbursementID is not None:
                result = await ReimbursementRepository.get_reimbursement_by_id(payment.reimbursementID)
                result_items = await ReimbursementRepository.get_reimbursement_items_by_reimbursement_id(payment.reimbursementID)
                if "error" in result:
                    log_error(f"Error fetching reimbursement with ID {payment.reimbursementID}: {result['error']}")
                    return {"error": result["error"], "status": result.get("status")}
                
                if "error" in result_items:
                    log_error(f"Error fetching reimbursement items for ID {payment.reimbursementID}: {result_items['error']}")
                    return {"error": result_items["error"], "status": result_items.get("status")}
                
                reimbursement = dict(result)
                reimbursement["items"] = result_items
            
            if payment.purchaseID is not None:
                purchase = await PurchaseRepository.get_by_id(payment.purchaseID)

                if "error" in purchase:
                    log_error(f"Error fetching purchase with ID {payment.purchaseID}: {purchase['error']}")
                    return {"error": purchase["error"], "status": purchase.get("status")}
                
            if payment.expenseID is not None:
                expense = await ExpenseRepository.get_by_id(payment.expenseID)
                
                if "error" in expense:
                    log_error(f"Error fetching expense with ID {payment.expenseID}: {payment['error']}")
                    return {"error": expense["error"], "status": expense.get('status')}
            
            if payment.salarySlipID is not None:
                salarySlip = await SalarySlipRepository.get_by_id(payment.salarySlipID)
                
                if "error" in salarySlip:
                    log_error(f"Error fetching salarySlip with ID {payment.salarySlipID}: {payment['error']}")
                    return {"error": expense["error"], "status": expense.get('status')}

            return {
                "payment": payment,
                "bankAccount": bankAccount,
                "purchase": purchase,
                "reimbursement": reimbursement,
                "expense": expense,
                "salarySlip": salarySlip
            }
        except Exception as e:
            log_error(f"Error retrieving payment: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_payments(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str):
        """
        Get all payments with pagination, filtering, and sorting.
        
        Args:
            page (int): The page number for pagination.
            pageSize (int): The number of items per page.
            filterObject (dict): The filter criteria for payments.
            sortBy (str): The field to sort by.
            sortByDirection (str): The direction of sorting ('asc' or 'desc').
        
        Returns:
            dict: A dictionary containing the payments and pagination info.
        """
        log_info(f"Retrieving payments with pagination: page={page}, pageSize={pageSize}, filter={filterObject}, sortBy={sortBy}, sortByDirection={sortByDirection}")
        
        try:
            result = await PaymentOutgoingRepository.get_payments(page, pageSize, filterObject, sortBy, sortByDirection)
            if "error" in result:
                log_error(f"Error fetching payments: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error retrieving payments: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_mutation_data(startDate: date, endDate: date, page: int, pageSize: int, bankAccountID: int):
        log_info(f"Retrieving payments with pagination: page={page}, pageSize={pageSize}, bankAccountID={bankAccountID}")
        try:
            result = await PaymentOutgoingRepository.get_mutation(
                startDate,
                endDate,
                page,
                pageSize,
                bankAccountID
            )
            if "error" in result:
                log_error(f"Error fetching payments: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error retrieving payments: {str(e)}")
            return internal_error()

    @staticmethod
    async def move_payment(id: int, date: str, userID: int, reason: str = ""):
        log_info(f"Moving payment with ID: {id} to date: {date}")
        try:
            payment = await PaymentOutgoingRepository.get_payment_by_id(id)
            if "error" in payment:
                log_error(f"Error fetching payment with ID {id}: {payment['error']}")
                return {"error": payment["error"], "status": payment.get("status", 500)}
            
            #Next check if payment isApprove || payment.isDelete, cannot move the date
            if payment.isApprove or payment.isDelete:
                return app_error(
                    ErrorCode.PAYMENT_LOCKED,
                    "Cannot move a payment that is approved or deleted",
                    400,
                )

            """
            Alasan wajib diisi.

            Memindahkan tanggal pembayaran berarti menunda uang keluar — dan
            pada saat audit, "mengapa dibayar mundur seminggu" adalah
            pertanyaan yang harus dapat dijawab dokumen, bukan ingatan.
            Tanggal lama ikut dicatat agar perubahannya terbaca utuh tanpa
            perlu menelusuri catatan lain.
            """
            alasan = (reason or "").strip()
            if not alasan:
                return app_error(
                    ErrorCode.VALIDATION,
                    "A reason is required when moving a payment date.",
                    400,
                )

            tanggal_lama = payment.date

            result = await PaymentOutgoingRepository.move_payment(
                id, date, userID, alasan, tanggal_lama
            )
            if "error" in result:
                log_error(f"Error moving payment: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error moving payment: {str(e)}")
            return internal_error()

    @staticmethod
    async def update_payment_status(
        id: int, status: str, userID: int, userLevel: int = 1
    ):
        """
        Update the status of a payment.
        
        Args:
            id (int): The ID of the payment to update.
            status (str): The new status of the payment.
            userID (int): The ID of the user updating the payment.
        
        Returns:
            dict: A success message or an error message.
        """
        log_info(f"Updating payment with ID: {id} to status: {status}")
        
        try:
            # First get the payment by ID to ensure it exists
            payment = await PaymentOutgoingRepository.get_payment_by_id(id)
            if "error" in payment:
                log_error(f"Error fetching payment with ID {id}: {payment['error']}")
                raise HTTPException(status_code=payment.get("status", 500), detail=payment["error"])
            if not payment:
                log_info(f"No payment found with ID: {id}")
                #raise HTTPException(status_code=404, detail="Payment not found")
                return {"error": "Payment not found", "status": 404}
            
            #If the payment is already approved or deleted, return an error
            if payment.isApprove or payment.isDelete:
                log_info(f"Payment with ID: {id} is already approved or deleted")
                #raise HTTPException(status_code=400, detail="Payment is already approved or deleted")
                return {"error": "Payment is already approved or deleted", "status": 400}

            # Aturan yang sama seperti persetujuan sekaligus: yang menyiapkan
            # uang bukan yang mengizinkan, dengan pengecualian pemilik usaha.
            #
            # Ditulis di kedua tempat karena keduanya adalah pintu yang
            # berbeda — persetujuan satu per satu dipakai dari kalender,
            # sedangkan yang sekaligus dari daftar pembayaran. Menjaga hanya
            # salah satunya berarti aturannya dapat dilewati lewat pintu lain.
            if (
                status == "approve"
                and payment.createdBy == userID
                and int(userLevel or 1) < 5
            ):
                return {
                    "error": (
                        "Pembayaran tidak dapat disetujui oleh pembuatnya "
                        "sendiri. Mintakan persetujuan kepada pengguna lain."
                    ),
                    "status": 403,
                }
            
            result = await PaymentOutgoingRepository.update_status(id, userID, status)
            if "error" in result:
                log_error(f"Error updating payment status: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            
            # Update the payment status in the database for the purchase
            if status == "approve":
                if payment.purchaseID is not None:
                    purchases = await PurchaseRepository.get_by_id(payment.purchaseID)
                    purchase_value = round(purchases["dpp"] + (purchases["ppn"] * purchases["dpp"] / 100) + purchases["pbbkb"] + purchases["otherValue"] - (purchases["pphPercentage"] * purchases["dpp"] / 100), 2)
                    
                    current_payments = await PaymentOutgoingRepository.get_payments_by_purchase_id(payment.purchaseID)
                    if "error" in current_payments:
                        log_error(f"Error fetching payments for purchase ID {payment.purchaseID}: {current_payments['error']}")
                        return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                    total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)
                    
                    #So the purchase_value is Decimal, while the total_paid is float
                    #How to convert the Decimal to float?
                    purchase_value = float(purchase_value)
                    total_paid = float(total_paid)

                    #If the difference is less than 5, then the purchase is fully paid
                    if abs(purchase_value - total_paid) < 5:
                        await PurchaseRepository.update_payment_status(payment.purchaseID, True)
                
                if payment.reimbursementID is not None:   
                    reimbursements = await ReimbursementRepository.get_reimbursement_items_by_reimbursement_id(payment.reimbursementID)
                    reimbursement_value = sum(r.amount for r in reimbursements)
                                        
                    current_payments = await PaymentOutgoingRepository.get_payments_by_reimbursement_id(payment.reimbursementID)
                    if "error" in current_payments:
                        log_error(f"Error fetching payments for reimbursement ID {payment.reimbursementID}: {current_payments['error']}")
                        return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                    total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)
                    
                    reimbursement_value = float(reimbursement_value)
                    total_paid = float(total_paid)
                    #If the difference is less than 5, then the reimbursement is fully paid
                    if abs(reimbursement_value - total_paid) < 5:
                        # `userID` ikut diteruskan; lihat catatan pada
                        # cabang beban di bawah.
                        await ReimbursementRepository.update_payment_status(
                            payment.reimbursementID, True, userID
                        )
                
                if payment.expenseID is not None:
                    expense = await ExpenseRepository.get_by_id(payment.expenseID)
                    expense_value = round(expense["dpp"] + expense["pbbkb"] - (expense["pphPercentage"] * expense["dpp"] / 100), 2)
                    
                    current_payments = await PaymentOutgoingRepository.get_payments_by_expense_id(payment.expenseID)
                    if "error" in current_payments:
                        log_error(f"Error fetching payments for expenseID ID {payment.expenseID}: {current_payments['error']}")
                        return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                    total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)
                    expense_value = float(expense_value)
                    # `total_paid` ikut dijadikan float.
                    #
                    # Nilainya dijumlahkan dari kolom DECIMAL sehingga
                    # bertipe Decimal, dan Python menolak mengurangkan
                    # Decimal dari float. Tiga cabang lain sudah
                    # mengubahnya; cabang inilah yang terlewat — dan
                    # persetujuan pembayaran pengeluaran selalu gagal
                    # dengan galat yang tidak menyebut cabangnya.
                    total_paid = float(total_paid)

                    #If the difference is less than 5, then the expense is fully paid
                    if abs(expense_value - total_paid) < 5:
                        # `userID` ikut diteruskan.
                        #
                        # Tanpa itu pemanggilannya kurang satu argumen dan
                        # persetujuan pembayaran beban selalu gagal. Cabang
                        # serupa di bawah sudah meneruskannya; yang ini
                        # terlewat.
                        await ExpenseRepository.update_payment_status(
                            payment.expenseID, True, userID
                        )

                if payment.salarySlipID is not None:
                    salarySlip = await SalarySlipRepository.get_by_id(payment.salarySlipID)
                    salarySlipAllowances = await SalarySlipAllowanceRepository.get_by_salary_slip_id(payment.salarySlipID)
                    salarySlipDeductions = await SalarySlipDeductionRepository.get_by_salary_slip_id(payment.salarySlipID)
                    
                    
                    salary_value = (
                        salarySlip["basicSalary"] + 
                        salarySlip["transportationAllowanceRate"] * salarySlip["transportationAllowanceQuantity"] + 
                        salarySlip["mealAllowanceRate"] * salarySlip["mealAllowanceQuantity"] + 
                        salarySlip["overtimeRate"] * salarySlip["overtimeQuantity"] + 
                        reduce(lambda x, y: x + y["amount"], salarySlipAllowances, 0) -
                        reduce(lambda x, y: x + y["amount"], salarySlipDeductions, 0) - 
                        salarySlip["taxAmount"]
                    )

                    current_payments = await PaymentOutgoingRepository.get_payments_by_salary_slip_id(payment.salarySlipID)
                    if "error" in current_payments:
                        log_error(f"Error fetching payments for expenseID ID {payment.expenseID}: {current_payments['error']}")
                        return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                    total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)

                    salary_value = float(salary_value)
                    total_paid = float(total_paid)
                    #If the difference is less than 5, then it means that the loan has been paid off
                    if abs(salary_value - total_paid) < 5:
                        await SalarySlipRepository.update_payment_status(payment.salarySlipID, True, userID)
                        
                if payment.loanID is not None:
                    loan = await LoanRepository.get_loan_by_id(payment.loanID)
                    if "error" in loan:
                        log_error(f"Error fetching loan for loanID ID {payment.loanID}: {loan['error']}")
                        return {"error": loan["error"], "status": loan.get("status", 500)}
                    loan_value = loan["debt"]
                    current_payments = await PaymentOutgoingRepository.get_payments_by_loan_id(payment.loanID)
                    if "error" in current_payments:
                        log_error(f"Error fetching payments for loanID ID {payment.loanID}: {current_payments['error']}")
                        return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                    total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)

                    loan_value = float(loan_value)
                    total_paid = float(total_paid)
                    #If the difference is less than 5, then it means that the loan has been paid off
                    if abs(loan_value - total_paid) < 5:
                        await LoanRepository.update_payment_status(payment.loanID, True, userID)
            
            log_info(f"Payment with ID: {id} updated successfully")
            return {"message": "Payment updated successfully"}
        except Exception as e:
            log_error(f"Error updating payment: {e}")
            return {"error": "Internal Server Error", "status": 500}

    @staticmethod
    async def update_bulk_payment_status(
        payment_ids: List[int], status: str, userID: int, userLevel: int = 1
    ):
        """
        Update the status of multiple payments in the database.
        
        Args:
            payment_ids (List[int]): A list of payment IDs to update.
            status (str): The new status of the payments.
            userID (int): The ID of the user updating the payments.
        
        Returns:
            dict: A success message or an error message.
        """
        log_info(f"Updating status for payments with IDs: {payment_ids}")
        
        try:
            payments = await PaymentOutgoingRepository.get_payments_by_ids(payment_ids)
            #Check if there is any payment that has been approved / deleted, if there is please return error
            for payment in payments:
                if payment.isDelete:
                    return {"error": "Payment has been deleted", "status": 400}
                if payment.isApprove:
                    return {"error": "Payment has been approved", "status": 400}

                # Yang menyiapkan uang bukan yang mengizinkan.
                #
                # Pemilik usaha dikecualikan. Pada perusahaan sekecil ini,
                # mewajibkan orang kedua untuk pembayaran yang dibuat pemilik
                # di luar jam kerja tidak menambah pengendalian — yang terjadi
                # justru pembayarannya diselesaikan di luar sistem, dan pada
                # saat itu tidak ada jejak sama sekali.
                #
                # Pengecualiannya bukan berarti tanpa catatan: persetujuan
                # atas dokumen sendiri ditandai tersendiri pada jejak
                # aktivitas, sehingga tetap dapat ditelusuri.
                if (
                    status == "approve"
                    and payment.createdBy == userID
                    and int(userLevel or 1) < 5
                ):
                    return {
                        "error": (
                            "Pembayaran tidak dapat disetujui oleh pembuatnya "
                            "sendiri. Mintakan persetujuan kepada pengguna lain."
                        ),
                        "status": 403,
                    }
            
            result = await PaymentOutgoingRepository.update_bulk_status(payment_ids, status, userID)
            if "error" in result:
                log_error(f"Error updating status for payments with IDs {payment_ids}: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            
            if status == "approve":
                for payment in payments:
                    if payment.purchaseID is not None:
                        purchases = await PurchaseRepository.get_by_id(payment.purchaseID)
                        purchase_value = round(purchases["dpp"] + (purchases["ppn"] * purchases["dpp"] / 100) + purchases["pbbkb"] + purchases["otherValue"] - (purchases["pphPercentage"] * purchases["dpp"] / 100), 2)
                        
                        current_payments = await PaymentOutgoingRepository.get_payments_by_purchase_id(payment.purchaseID)
                        if "error" in current_payments:
                            log_error(f"Error fetching payments for purchase ID {payment.purchaseID}: {current_payments['error']}")
                            return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                        total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)

                        purchase_value = float(purchase_value)
                        total_paid = float(total_paid)
                        
                        #If the difference is less than 5, then the payment is considered complete
                        if abs(purchase_value - total_paid) < 5:
                            await PurchaseRepository.update_payment_status(payment.purchaseID, True)
                    
                    if payment.reimbursementID is not None:   
                        reimbursements = await ReimbursementRepository.get_reimbursement_items_by_reimbursement_id(payment.reimbursementID)
                        reimbursement_value = sum(r.amount for r in reimbursements)
                                            
                        current_payments = await PaymentOutgoingRepository.get_payments_by_reimbursement_id(payment.reimbursementID)
                        if "error" in current_payments:
                            log_error(f"Error fetching payments for reimbursement ID {payment.reimbursementID}: {current_payments['error']}")
                            return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                        total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)

                        reimbursement_value = float(reimbursement_value)
                        total_paid = float(total_paid)
                        
                        if(abs(reimbursement_value - total_paid) < 5):
                            await ReimbursementRepository.update_payment_status(payment.reimbursementID, True, userID)
                    
                    if payment.expenseID is not None:
                        expense = await ExpenseRepository.get_by_id(payment.expenseID)
                        expense_value = round(expense["dpp"] + expense["pbbkb"] - (expense["pphPercentage"] * expense["dpp"] / 100), 2)
                        
                        current_payments = await PaymentOutgoingRepository.get_payments_by_expense_id(payment.expenseID)
                        if "error" in current_payments:
                            log_error(f"Error fetching payments for expenseID ID {payment.expenseID}: {current_payments['error']}")
                            return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                        total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)

                        expense_value = float(expense_value)
                        total_paid = float(total_paid)
                        
                        #If the difference is less than 5, then the payment is considered complete
                        if abs(expense_value - total_paid) < 5:
                            await ExpenseRepository.update_payment_status(payment.expenseID, True, userID)

                    if payment.salarySlipID is not None:
                        salarySlip = await SalarySlipRepository.get_by_id(payment.salarySlipID)
                        salarySlipAllowances = await SalarySlipAllowanceRepository.get_by_salary_slip_id(payment.salarySlipID)
                        salarySlipDeductions = await SalarySlipDeductionRepository.get_by_salary_slip_id(payment.salarySlipID)
                        
                        
                        salary_value = (
                            salarySlip["basicSalary"] + 
                            salarySlip["transportationAllowanceRate"] * salarySlip["transportationAllowanceQuantity"] + 
                            salarySlip["mealAllowanceRate"] * salarySlip["mealAllowanceQuantity"] + 
                            salarySlip["overtimeRate"] * salarySlip["overtimeQuantity"] + 
                            reduce(lambda x, y: x + y["amount"], salarySlipAllowances, 0) -
                            reduce(lambda x, y: x + y["amount"], salarySlipDeductions, 0) - 
                            salarySlip["taxAmount"]
                        )

                        current_payments = await PaymentOutgoingRepository.get_payments_by_salary_slip_id(payment.salarySlipID)
                        if "error" in current_payments:
                            log_error(f"Error fetching payments for expenseID ID {payment.expenseID}: {current_payments['error']}")
                            return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                        total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)

                        salary_value = float(salary_value)
                        total_paid = float(total_paid)
                        
                        #If the difference is less than 5, then the payment is considered complete
                        if abs(salary_value - total_paid) < 5:
                            await SalarySlipRepository.update_payment_status(payment.salarySlipID, True, userID)
                            
                    if payment.loanID is not None:
                        loan = await LoanRepository.get_loan_by_id(payment.loanID)
                        if "error" in loan:
                            log_error(f"Error fetching loan for loanID ID {payment.loanID}: {loan['error']}")
                            return {"error": loan["error"], "status": loan.get("status", 500)}
                        loan_value = loan["debt"]
                        current_payments = await PaymentOutgoingRepository.get_payments_by_loan_id(payment.loanID)
                        if "error" in current_payments:
                            log_error(f"Error fetching payments for loanID ID {payment.loanID}: {current_payments['error']}")
                            return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                        total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)

                        loan_value = float(loan_value)
                        total_paid = float(total_paid)
                        
                        #If the difference is less than 5, then the payment is considered complete
                        if abs(loan_value - total_paid) < 5:
                            await LoanRepository.update_payment_status(payment.loanID, True, userID)
                
            return result
        except Exception as e:
            log_error(f"Error updating status for payments with IDs {payment_ids}: {str(e)}")
            return internal_error()

    @staticmethod
    async def selaraskan_dokumen(jenis: str, dokumen_id: int, userID: int):
        """
        Hitung ulang status lunas satu dokumen, atas permintaan pengguna.

        Diperlukan karena penyelarasan otomatis dapat tertinggal: bila
        penulisan status gagal setelah pembayarannya tersimpan — koneksi
        putus, server sedang padat — dokumennya tetap bertanda lama, dan
        tidak ada yang mengulanginya sendiri.

        Menghitung ulang selalu aman: hasilnya diturunkan dari pembayaran
        yang tersimpan, bukan ditambahkan padanya. Menjalankannya dua kali
        memberi hasil yang sama.
        """

        class _Sasaran:
            """Meniru bentuk baris pembayaran; hanya id dokumennya yang dipakai."""

            purchaseID = None
            reimbursementID = None
            expenseID = None
            salarySlipID = None
            loanID = None

        peta = {
            "purchase": "purchaseID",
            "reimbursement": "reimbursementID",
            "expense": "expenseID",
            "salary_slip": "salarySlipID",
            "loan": "loanID",
        }
        kolom = peta.get(jenis)
        if not kolom:
            return app_error(
                ErrorCode.VALIDATION,
                "Jenis dokumen tidak dikenal.",
                400,
            )

        sasaran = _Sasaran()
        setattr(sasaran, kolom, dokumen_id)
        await PaymentOutgoingController.selaraskan_status_lunas(sasaran, userID)
        return {"message": "Status pembayaran diselaraskan."}

    @staticmethod
    async def selaraskan_status_lunas(payment, userID: int | None = None):
        """
        Hitung ulang status lunas dokumen yang ditagih sebuah pembayaran.

        Dihitung DUA ARAH: menjadi lunas bila pembayarannya cukup, dan
        kembali belum lunas bila tidak. Sebelumnya statusnya hanya pernah
        disetel menjadi lunas — sehingga pembayaran yang dibatalkan
        meninggalkan dokumen bertanda lunas padahal uangnya tidak keluar.

        Toleransi 5 rupiah, sama seperti pada persetujuan pembayaran:
        pembulatan pajak menyisakan selisih beberapa rupiah yang bukan
        kekurangan bayar.

        Satu pembayaran hanya menagih SATU jenis dokumen; percabangan di
        bawah karena itu saling meniadakan, bukan menumpuk.
        """
        def lunas(nilai, terbayar) -> bool:
            return abs(float(nilai) - float(terbayar)) < 5

        def jumlah(daftar) -> float:
            return float(
                sum(p.amount for p in daftar if p.isApprove and not p.isDelete)
            )

        try:
            if payment.purchaseID is not None:
                d = await PurchaseRepository.get_by_id(payment.purchaseID)
                nilai = round(
                    d["dpp"] + (d["ppn"] * d["dpp"] / 100) + (d["pbbkb"] or 0), 2
                )
                bayar = await PaymentOutgoingRepository.get_payments_by_purchase_id(
                    payment.purchaseID
                )
                if not isinstance(bayar, dict):
                    await PurchaseRepository.update_payment_status(
                        payment.purchaseID, lunas(nilai, jumlah(bayar))
                    )

            elif payment.reimbursementID is not None:
                items = await ReimbursementRepository.get_reimbursement_items_by_reimbursement_id(
                    payment.reimbursementID
                )
                nilai = sum(r.amount for r in items)
                bayar = await PaymentOutgoingRepository.get_payments_by_reimbursement_id(
                    payment.reimbursementID
                )
                if not isinstance(bayar, dict):
                    await ReimbursementRepository.update_payment_status(
                        payment.reimbursementID, lunas(nilai, jumlah(bayar)), userID
                    )

            elif payment.expenseID is not None:
                d = await ExpenseRepository.get_expense_by_id(payment.expenseID)
                nilai = d["amount"] if not isinstance(d, dict) or "amount" in d else 0
                bayar = await PaymentOutgoingRepository.get_payments_by_expense_id(
                    payment.expenseID
                )
                if not isinstance(bayar, dict):
                    await ExpenseRepository.update_payment_status(
                        payment.expenseID, lunas(nilai, jumlah(bayar)), userID
                    )

            elif payment.salarySlipID is not None:
                bayar = await PaymentOutgoingRepository.get_payments_by_salary_slip_id(
                    payment.salarySlipID
                )
                d = await SalarySlipRepository.get_salary_slip_by_id(
                    payment.salarySlipID
                )
                nilai = d["total"] if isinstance(d, dict) and "total" in d else 0
                if not isinstance(bayar, dict):
                    await SalarySlipRepository.update_payment_status(
                        payment.salarySlipID, lunas(nilai, jumlah(bayar)), userID
                    )

            elif payment.loanID is not None:
                pinjaman = await LoanRepository.get_loan_by_id(payment.loanID)
                nilai = pinjaman["debt"] if isinstance(pinjaman, dict) else 0
                bayar = await PaymentOutgoingRepository.get_payments_by_loan_id(
                    payment.loanID
                )
                if not isinstance(bayar, dict):
                    await LoanRepository.update_payment_status(
                        payment.loanID, lunas(nilai, jumlah(bayar)), userID
                    )
        except Exception as e:
            # Kegagalan penyelarasan TIDAK menggagalkan tindakan utamanya;
            # yang terjadi hanya statusnya tertinggal, dan itu dapat
            # diperbaiki lewat penyelarasan ulang.
            log_error(f"Gagal menyelaraskan status lunas: {e}")

    @staticmethod
    async def delete_payment_by_id(id: int, userID: int | None = None):
        """
        Delete a payment by ID.
        
        Args:
            id (int): The ID of the payment to delete.
        
        Returns:
            dict: A success message or an error message.
        """
        log_info(f"Deleting payment with ID: {id}")
        
        try:
            payment = await PaymentOutgoingRepository.get_payment_by_id(id)
            if "error" in payment:
                log_error(f"Error fetching payment with ID {id}: {payment['error']}")
                return {"error": payment["error"], "status": payment.get("status", 500)}
            
            # Fungsi ini SEBELUMNYA hanya membaca lalu melaporkan sukses.
            #
            # Tidak ada rute yang memanggilnya, sehingga tidak berakibat apa
            # pun — tetapi laporan sukses tanpa perbuatan adalah jebakan bagi
            # siapa pun yang kelak menyambungkannya.
            hasil = await PaymentOutgoingRepository.soft_delete_payment(id, userID)
            if isinstance(hasil, dict) and "error" in hasil:
                log_error(f"Error deleting payment with ID {id}: {hasil['error']}")
                return hasil

            # Status lunas dokumen yang ditagih dihitung ULANG.
            #
            # Menghapus pembayaran mengurangi jumlah yang sudah dibayarkan;
            # tanpa perhitungan ulang, dokumennya tetap bertanda lunas
            # padahal uangnya tidak pernah keluar.
            await PaymentOutgoingController.selaraskan_status_lunas(payment)

            log_info(f"Payment with ID: {id} deleted successfully")
            return {"message": "Payment deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting payment: {e}")
            return {"error": "Internal server error", "status": 500}
        
        
    @staticmethod
    async def get_calendar_data_by_date(date: d, bankAccounts: List[int] | None):
        log_info(f"Retrieving calendar data for payments for date {str(d)}")

        day = date.day
        month = date.month
        year = date.year

        try:
            """
            Tiga kueri pertama dijalankan bersamaan.

            Rekening, pembayaran, dan transfer antar rekening tidak saling
            bergantung; hanya saldo awal yang menunggu, karena butuh daftar
            id rekening. Jadi empat kueri berurutan menjadi dua putaran.
            """
            accounts, result, interpayments = await asyncio.gather(
                BankAccount.get_bank_accounts_by_ids(bankAccounts),
                PaymentOutgoingRepository.get_calendar_data_by_date(day, month, year, bankAccounts),
                InterpaymentRepository.get_calendar_data_by_date(day, month, year, bankAccounts),
            )

            for nama, hasil in (
                ("bank accounts", accounts),
                ("payment outgoing", result),
                ("interpayments", interpayments),
            ):
                if isinstance(hasil, dict) and "error" in hasil:
                    log_error(f"Error fetching {nama} in calendar data: {hasil['error']}")
                    return {"error": hasil["error"], "status": hasil.get("status", 500)}
            
            # Accounts come back as pydantic models -> work with plain dicts
            # so we can attach balance and fee estimates to them.
            accounts = [
                a if isinstance(a, dict) else a.model_dump()
                for a in accounts
            ]

            # --- opening balance per account -------------------------------
            account_ids = [a["id"] for a in accounts]
            balances = await Balance.fetch_by_bank_account_ids(account_ids)
            balance_map = {}
            if isinstance(balances, list):
                balance_map = {b["id"]: (b["balance"] or 0) for b in balances}

            # --- estimated inter-bank transfer fee --------------------------
            # A transfer to an account at the SAME bank is free; a transfer to
            # another bank costs INTERBANK_TRANSFER_FEE per transaction.
            def _same_bank(origin, destination) -> bool:
                if not origin or not destination:
                    return False
                return str(origin).strip().lower() == str(destination).strip().lower()

            for account in accounts:
                account_payments = [
                    p for p in result
                    if p.get("bankAccountID") == account["id"]
                    and not p.get("isDelete")
                ]
                interbank_count = 0
                same_bank_count = 0
                unknown_count = 0
                for payment in account_payments:
                    destination = payment.get("destinationBankName")
                    if not destination:
                        # unknown destination -> assume worst case (charged)
                        unknown_count += 1
                        interbank_count += 1
                    elif _same_bank(account.get("bankName"), destination):
                        same_bank_count += 1
                    else:
                        interbank_count += 1

                total_payment = sum(
                    (p.get("amount") or 0) for p in account_payments
                )
                opening_balance = balance_map.get(account["id"], 0)
                admin_fee = interbank_count * INTERBANK_TRANSFER_FEE

                account["balance"] = opening_balance
                account["openingBalance"] = opening_balance
                account["totalPaymentAmount"] = total_payment
                account["interbankTransferCount"] = interbank_count
                account["sameBankTransferCount"] = same_bank_count
                account["unknownDestinationCount"] = unknown_count
                account["estimatedAdminFee"] = admin_fee
                account["closingBalance"] = (
                    opening_balance - total_payment - admin_fee
                )

            return {
                "data": result,
                "bankAccounts": accounts,
                "interpayments": interpayments,
                "interbankTransferFee": INTERBANK_TRANSFER_FEE
            }
        except Exception as e:
            log_error(f"Error retrieving calendar data: {str(e)}")
            return internal_error()
        
    @staticmethod
    async def get_calendar_selector_by_date(date: d, bankAccounts: List[int] | None):
        log_info(f"Retrieving calendar data for payments for date {str(d)}")

        day = date.day
        month = date.month
        year = date.year

        try:
            accounts = await BankAccount.get_bank_accounts_by_ids(bankAccounts)
            if "error" in accounts:
                log_error(f"Error fetching bank accounts in calendar data: {accounts['error']}")
                return {"error": accounts["error"], "status": accounts.get('status', 500)}

            result = await PaymentOutgoingRepository.get_calendar_data_by_date(day, month, year, bankAccounts)
            if "error" in result:
                log_error(f"Error fetching payment outgoing in calendar data: {result['error']}")
                return {"error": result["error"], "status": result.get('status', 500)}

            interpayments = await InterpaymentRepository.get_calendar_data_by_date(day, month, year,bankAccounts)
            if "error" in interpayments:
                log_error(f"Error fetching interpayments in calendar data: {interpayments['error']}")
                return {"error": interpayments["error"], "status": interpayments.get('status', 500)}
            
            return {
                "data": result,
                "bankAccounts": accounts,
                "interpayments": interpayments
            }
        except Exception as e:
            log_error(f"Error retrieving calendar data: {str(e)}")
            return internal_error()
        
    @staticmethod
    async def get_pph_report(month: int, year: int):
        try:
            purchase = await PaymentOutgoingRepository.get_purchase_pph_report(month, year)
            if "error" in purchase:
                log_error(f"Error fetching purchase PPH report data: {purchase['error']}")
                return {"error": purchase["error"], "status": purchase.get('status', 500)}
            
            expense = await PaymentOutgoingRepository.get_expense_pph_report(month, year)
            if "error" in expense:
                log_error(f"Error fetching expense PPH report data: {expense['error']}")
                return {"error": expense["error"], "status": expense.get('status', 500)}

            return {
                "purchase": purchase,
                "expense": expense
            }
        except Exception as e:
            log_error(f"Error retrieving calendar data: {str(e)}")
            return internal_error()