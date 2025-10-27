from sqlalchemy import func, insert, select, update, delete, or_
from utils.database import database
from models.payment_outgoing_model import PaymentOutgoing
from repository.purchase_repository import PurchaseRepository
from repository.reimbursement_repository import ReimbursementRepository
from repository.salary_slip_repository import SalarySlipRepository, SalarySlipAllowanceRepository, SalarySlipDeductionRepository
from repository.expense_repository import ExpenseRepository
from repository.bank_account_repository import BankAccount
from repository.interpayment_repository import InterpaymentRepository
from repository.loan_repository import LoanRepository
from utils.logger_utils import log_error, log_info
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
            result = await PaymentOutgoing.create(payment_data)
            if "error" in result:
                log_error(f"Error creating payment: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error creating payment: {str(e)}")
            return {"error": str(e), "status": 500}
        
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
            payments = await PaymentOutgoing.get_payments_by_purchase_id(purchase_id)
            if "error" in payments:
                log_error(f"Error fetching payments for purchase ID {purchase_id}: {payments['error']}")
                return {"error": payments["error"], "status": payments.get("status", 500)}
            
            log_info(f"Retrieved {len(payments)} payments for purchase ID: {purchase_id}")
            return {"payments": payments}
        except Exception as e:
            log_error(f"Error retrieving payments: {str(e)}")
            return {"error": str(e), "status": 500}
    
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
            payment = await PaymentOutgoing.get_payment_by_id(id)
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
            return {"error": str(e), "status": 500}

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
            result = await PaymentOutgoing.get_payments(page, pageSize, filterObject, sortBy, sortByDirection)
            if "error" in result:
                log_error(f"Error fetching payments: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error retrieving payments: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_mutation_data(startDate: date, endDate: date, page: int, pageSize: int, bankAccountID: int):
        log_info(f"Retrieving payments with pagination: page={page}, pageSize={pageSize}, bankAccountID={bankAccountID}")
        try:
            result = await PaymentOutgoing.get_mutation(
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
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update_payment_status(id: int, status: str, userID: int):
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
            payment = await PaymentOutgoing.get_payment_by_id(id)
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
            
            result = await PaymentOutgoing.update_status(id, userID, status)
            if "error" in result:
                log_error(f"Error updating payment status: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            
            # Update the payment status in the database for the purchase
            if status == "approve":
                if payment.purchaseID is not None:
                    purchases = await PurchaseRepository.get_by_id(payment.purchaseID)
                    purchase_value = round(purchases["dpp"] + (purchases["ppn"] * purchases["dpp"] / 100) + purchases["pbbkb"] + purchases["otherValue"] - (purchases["pphPercentage"] * purchases["dpp"] / 100), 2)
                    
                    current_payments = await PaymentOutgoing.get_payments_by_purchase_id(payment.purchaseID)
                    if "error" in current_payments:
                        log_error(f"Error fetching payments for purchase ID {payment.purchaseID}: {current_payments['error']}")
                        return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                    total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)
                    
                    if purchase_value == total_paid:
                        await PurchaseRepository.update_payment_status(payment.purchaseID, True)
                
                if payment.reimbursementID is not None:   
                    reimbursements = await ReimbursementRepository.get_reimbursement_items_by_reimbursement_id(payment.reimbursementID)
                    reimbursement_value = sum(r.amount for r in reimbursements)
                                        
                    current_payments = await PaymentOutgoing.get_payments_by_reimbursement_id(payment.reimbursementID)
                    if "error" in current_payments:
                        log_error(f"Error fetching payments for reimbursement ID {payment.reimbursementID}: {current_payments['error']}")
                        return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                    total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)
                    
                    if reimbursement_value == total_paid:
                        await ReimbursementRepository.update_payment_status(payment.reimbursementID, True, userID)
                
                if payment.expenseID is not None:
                    expense = await ExpenseRepository.get_by_id(payment.expenseID)
                    expense_value = round(expense["dpp"] + expense["pbbkb"] - (expense["pphPercentage"] * expense["dpp"] / 100), 2)
                    
                    current_payments = await PaymentOutgoing.get_payments_by_expense_id(payment.expenseID)
                    if "error" in current_payments:
                        log_error(f"Error fetching payments for expenseID ID {payment.expenseID}: {current_payments['error']}")
                        return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                    total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)
                    
                    if expense_value == total_paid:
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

                    current_payments = await PaymentOutgoing.get_payments_by_salary_slip_id(payment.salarySlipID)
                    if "error" in current_payments:
                        log_error(f"Error fetching payments for expenseID ID {payment.expenseID}: {current_payments['error']}")
                        return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                    total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)
                    
                    if salary_value == total_paid:
                        await SalarySlipRepository.update_payment_status(payment.salarySlipID, True, userID)
                        
                if payment.loanID is not None:
                    loan = await LoanRepository.get_loan_by_id(payment.loanID)
                    if "error" in loan:
                        log_error(f"Error fetching loan for loanID ID {payment.loanID}: {loan['error']}")
                        return {"error": loan["error"], "status": loan.get("status", 500)}
                    loan_value = loan["amount"]
                    current_payments = await PaymentOutgoing.get_payments_by_loan_id(payment.loanID)
                    if "error" in current_payments:
                        log_error(f"Error fetching payments for loanID ID {payment.loanID}: {current_payments['error']}")
                        return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                    total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)
                    
                    if loan_value == total_paid:
                        await LoanRepository.update_payment_status(payment.loanID, True, userID)
            
            log_info(f"Payment with ID: {id} updated successfully")
            return {"message": "Payment updated successfully"}
        except Exception as e:
            log_error(f"Error updating payment: {e}")
            return {"error": "Internal Server Error", "status": 500}

    @staticmethod
    async def update_bulk_payment_status(payment_ids: List[int], status: str, userID: int):
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
            payments = await PaymentOutgoing.get_payments_by_ids(payment_ids)
            #Check if there is any payment that has been approved / deleted, if there is please return error
            for payment in payments:
                if payment.isDelete:
                    return {"error": "Payment has been deleted", "status": 400}
                if payment.isApprove:
                    return {"error": "Payment has been approved", "status": 400}
            
            result = await PaymentOutgoing.update_bulk_status(payment_ids, status, userID)
            if "error" in result:
                log_error(f"Error updating status for payments with IDs {payment_ids}: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            
            if status == "approve":
                for payment in payments:
                    if payment.purchaseID is not None:
                        purchases = await PurchaseRepository.get_by_id(payment.purchaseID)
                        purchase_value = round(purchases["dpp"] + (purchases["ppn"] * purchases["dpp"] / 100) + purchases["pbbkb"] + purchases["otherValue"] - (purchases["pphPercentage"] * purchases["dpp"] / 100), 2)
                        
                        current_payments = await PaymentOutgoing.get_payments_by_purchase_id(payment.purchaseID)
                        if "error" in current_payments:
                            log_error(f"Error fetching payments for purchase ID {payment.purchaseID}: {current_payments['error']}")
                            return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                        total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)
                        
                        if purchase_value == total_paid:
                            await PurchaseRepository.update_payment_status(payment.purchaseID, True)
                    
                    if payment.reimbursementID is not None:   
                        reimbursements = await ReimbursementRepository.get_reimbursement_items_by_reimbursement_id(payment.reimbursementID)
                        reimbursement_value = sum(r.amount for r in reimbursements)
                                            
                        current_payments = await PaymentOutgoing.get_payments_by_reimbursement_id(payment.reimbursementID)
                        if "error" in current_payments:
                            log_error(f"Error fetching payments for reimbursement ID {payment.reimbursementID}: {current_payments['error']}")
                            return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                        total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)
                        
                        if reimbursement_value == total_paid:
                            await ReimbursementRepository.update_payment_status(payment.reimbursementID, True, userID)
                    
                    if payment.expenseID is not None:
                        expense = await ExpenseRepository.get_by_id(payment.expenseID)
                        expense_value = round(expense["dpp"] + expense["pbbkb"] - (expense["pphPercentage"] * expense["dpp"] / 100), 2)
                        
                        current_payments = await PaymentOutgoing.get_payments_by_expense_id(payment.expenseID)
                        if "error" in current_payments:
                            log_error(f"Error fetching payments for expenseID ID {payment.expenseID}: {current_payments['error']}")
                            return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                        total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)
                        
                        if expense_value == total_paid:
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

                        current_payments = await PaymentOutgoing.get_payments_by_salary_slip_id(payment.salarySlipID)
                        if "error" in current_payments:
                            log_error(f"Error fetching payments for expenseID ID {payment.expenseID}: {current_payments['error']}")
                            return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                        total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)
                        
                        if salary_value == total_paid:
                            await SalarySlipRepository.update_payment_status(payment.salarySlipID, True, userID)
                            
                    if payment.loanID is not None:
                        loan = await LoanRepository.get_loan_by_id(payment.loanID)
                        if "error" in loan:
                            log_error(f"Error fetching loan for loanID ID {payment.loanID}: {loan['error']}")
                            return {"error": loan["error"], "status": loan.get("status", 500)}
                        loan_value = loan["amount"]
                        current_payments = await PaymentOutgoing.get_payments_by_loan_id(payment.loanID)
                        if "error" in current_payments:
                            log_error(f"Error fetching payments for loanID ID {payment.loanID}: {current_payments['error']}")
                            return {"error": current_payments["error"], "status": current_payments.get("status", 500)}
                        total_paid = sum(p.amount for p in current_payments if p.isApprove and not p.isDelete)
                        
                        if loan_value == total_paid:
                            await LoanRepository.update_payment_status(payment.loanID, True, userID)
                
            return result
        except Exception as e:
            log_error(f"Error updating status for payments with IDs {payment_ids}: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def delete_payment_by_id(id: int):
        """
        Delete a payment by ID.
        
        Args:
            id (int): The ID of the payment to delete.
        
        Returns:
            dict: A success message or an error message.
        """
        log_info(f"Deleting payment with ID: {id}")
        
        try:
            payment = await PaymentOutgoing.get_payment_by_id(id)
            if "error" in payment:
                log_error(f"Error fetching payment with ID {id}: {payment['error']}")
                return {"error": payment["error"], "status": payment.get("status", 500)}
            
            log_info(f"Payment with ID: {id} deleted successfully")
            return {"message": "Payment deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting payment: {e}")
            return {"error": "Internal server error", "status": 500}
        
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
            result = await PaymentOutgoing.get_calendar_data(month, year, bankAccounts)
            if "error" in result:
                log_error(f"Error fetching calendar data: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}
            
            interpayments = await InterpaymentRepository.get_calendar_data(month, year, bankAccounts)
            if "error" in interpayments:
                log_error(f"Error fetching interpayment calendar data: {result['error']}")
                return {"error": result["error"], "status": result.get("status", 500)}

            
            return {
                "payments": result,
                "interpayments": interpayments,
            }
        except Exception as e:
            log_error(f"Error retrieving calendar data: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_calendar_data_by_date(date: d, bankAccounts: List[int] | None):
        log_info(f"Retrieving calendar data for payments for date {str(d)}")

        day = date.day
        month = date.month
        year = date.year

        try:
            accounts = await BankAccount.get_bank_accounts_by_ids(bankAccounts)
            if "error" in accounts:
                log_error(f"Error fetching bank accounts in calendar data: {accounts['error']}")
                return {"error": accounts["error"], "status": accounts.get('status', 500)}

            result = await PaymentOutgoing.get_calendar_data_by_date(day, month, year, bankAccounts)
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
            return {"error": str(e), "status": 500}
        
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

            result = await PaymentOutgoing.get_calendar_data_by_date(day, month, year, bankAccounts)
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
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_pph_report(month: int, year: int):
        try:
            purchase = await PaymentOutgoing.get_purchase_pph_report(month, year)
            if "error" in purchase:
                log_error(f"Error fetching purchase PPH report data: {purchase['error']}")
                return {"error": purchase["error"], "status": purchase.get('status', 500)}
            
            expense = await PaymentOutgoing.get_expense_pph_report(month, year)
            if "error" in expense:
                log_error(f"Error fetching expense PPH report data: {expense['error']}")
                return {"error": expense["error"], "status": expense.get('status', 500)}

            return {
                "purchase": purchase,
                "expense": expense
            }
        except Exception as e:
            log_error(f"Error retrieving calendar data: {str(e)}")
            return {"error": str(e), "status": 500}