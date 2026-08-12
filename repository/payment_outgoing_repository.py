from typing import List
from sqlalchemy import String, or_, select, func, and_, case, literal
from utils.database import database
from datetime import date as d, datetime as dt, timedelta
from models.payment_outgoing_model import payments_outgoing_table, PaymentOutgoing
from models.purchase_model import purchases_table
from models.reimbursement_model import reimbursements_table
from models.salary_slip_model import salary_slips_table
from models.employee_model import employees_table
from models.expense_model import expenses_table
from models.expense_opponent_model import expense_opponents_table
from models.supplier_model import suppliers_table
from models.bank_model import bank_accounts_table
from models.loans_model import loans_table
from utils.logger_utils import log_error, log_info


def _month_start(month: int, year: int) -> d:
    return d(year, month, 1)


def _month_end(month: int, year: int) -> d:
    # exclusive upper bound = first day of next month
    return d(year + 1, 1, 1) if month == 12 else d(year, month + 1, 1)


def _day_start(day: int, month: int, year: int) -> d:
    return d(year, month, day)


def _day_end(day: int, month: int, year: int) -> d:
    return d(year, month, day) + timedelta(days=1)


class PaymentOutgoingRepository:
    @staticmethod
    async def create(payment_data: dict):
        """
        Create a new payment in the database.
        
        Returns:
            dict: A success message with the created payment ID.
        """
        try:
            query = payments_outgoing_table.insert().values(payment_data)
            result = await database.execute(query)
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="payment_outgoing",
                entityID=result,
                action="create",
            )

            # Pembayaran yang melunasi dokumen lain juga dicatat pada dokumen
            # itu sendiri. Tanpa ini, riwayat pinjaman/pembelian tidak
            # menunjukkan apa pun saat cicilannya dibayar — padahal di situlah
            # orang mencarinya.
            _induk = [
                ("loans", payment_data.get("loanID")),
                ("purchases", payment_data.get("purchaseID")),
                ("expenses", payment_data.get("expenseID")),
                ("reimbursements", payment_data.get("reimbursementID")),
                ("salary_slips", payment_data.get("salarySlipID")),
            ]
            for _entitas, _id in _induk:
                if not _id:
                    continue
                await AuditLogRepository.record(
                    entity=_entitas,
                    entityID=_id,
                    action="payment",
                    changes={
                        "amount": {
                            "from": None,
                            "to": payment_data.get("amount"),
                        }
                    },
                )

            return {"message": "Payment created successfully", "payment_id": result}
        except Exception as e:
            log_error(f"Error creating payment: {str(e)}")
            return {"error": str(e), "status": 500}
    
    @staticmethod
    async def get_payments(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str):
        """
        Get all payments with pagination, filtering, and sorting.
        
        Args:
            page (int): The page number for pagination.
            pageSize (int): The number of items per page.
            filterObject (dict): The filter criteria for the payments.
            sortBy (str): The field to sort by.
            sortByDirection (str): The direction of sorting ('asc' or 'desc').
            keyword (str | None): A keyword to search in the payments.
        
        Returns:
            dict: A dictionary containing the payments and pagination info.
        """
        # Placeholder for actual implementation
        # SELECT payments.*, COALESCE(purchases.invoiceName, reimbursements.name) AS documetName

        or_conditions = []
        if filterObject.get("isApproved"):
            or_conditions.append(payments_outgoing_table.c.isApprove == True)
        if filterObject.get("isPending"):
            or_conditions.append(
                and_(
                    payments_outgoing_table.c.isApprove == False,
                    payments_outgoing_table.c.isDelete == False
                )
            )
        if filterObject.get("isRejected"):
            or_conditions.append(payments_outgoing_table.c.isDelete == True)

        month_names = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }

        month_case = case(
            *( (salary_slips_table.c.month == num, name) for num, name in month_names.items() ),
            else_=literal('Unknown')
        )
        
        query = select(
            payments_outgoing_table,
            func.coalesce(
                purchases_table.c.invoiceName, 
                reimbursements_table.c.name,
                func.concat(
                    literal('Salary '),
                    employees_table.c.name,
                    literal(' '),
                    month_case,
                    literal(' '),
                    salary_slips_table.c.year.cast(String)
                ), 
                expenses_table.c.invoiceName
            ).label("documentName"),
            bank_accounts_table.c.bankAccountName.label("bankAccountName"),
            bank_accounts_table.c.bankAccountNumber.label("bankAccountNumber"),
            bank_accounts_table.c.bankName.label("bankName")
        ).outerjoin(
            purchases_table, payments_outgoing_table.c.purchaseID == purchases_table.c.id
        ).outerjoin(
            reimbursements_table, payments_outgoing_table.c.reimbursementID == reimbursements_table.c.id
        ).outerjoin(
            salary_slips_table, payments_outgoing_table.c.salarySlipID == salary_slips_table.c.id
        ).outerjoin(
            employees_table, salary_slips_table.c.userID == employees_table.c.id
        ).outerjoin(
            expenses_table, payments_outgoing_table.c.expenseID == expenses_table.c.id
        ).outerjoin(
            bank_accounts_table, payments_outgoing_table.c.bankAccountID == bank_accounts_table.c.id
        ).where(
            or_(*or_conditions)
        ).limit(pageSize).offset((page - 1) * pageSize)

        
        if sortBy == "date":
            if sortByDirection == "desc":
                query = query.order_by(payments_outgoing_table.c.date.desc())
            else:
                query = query.order_by(payments_outgoing_table.c.date.asc())
        elif sortBy == "amount":
            if sortByDirection == "desc":
                query = query.order_by(payments_outgoing_table.c.amount.desc())
            else:
                query = query.order_by(payments_outgoing_table.c.amount.asc())
        else:
            query = query.order_by(payments_outgoing_table.c.date.desc())
    
        result = await database.fetch_all(query)
        
        #Not the count
        total_query = select(func.count()).select_from(payments_outgoing_table).where(
            or_(*or_conditions))
        total = await database.fetch_val(total_query)

        return {
            "data": result,
            "count": total
        }
        

        # or_conditions = []
        # if(keyword is not None and keyword != ""):
        #     or_conditions.append(purchases_table.c.purchaseOrderName.ilike(f"%{keyword}%"))
        #     or_conditions.append(purchases_table.c.invoiceName.ilike(f"%{keyword}%"))
        #     or_conditions.append(purchases_table.c.receiptName.ilike(f"%{keyword}%"))
        #     or_conditions.append(purchases_table.c.taxInvoiceName.ilike(f"%{keyword}%"))
        #     or_conditions.append(suppliers_table.c.name.ilike(f"%{keyword}%"))
        # conditions.append(or_(*or_conditions))

    @staticmethod
    async def get_mutation(startDate: d, endDate: d, page: int, pageSize: int, bankAccountID: int):
        select_columns = [
            payments_outgoing_table,  # Selects all columns from interpayment_table
            purchases_table.c.invoiceName.label("purchase_invoiceName"),
            purchases_table.c.date.label("purchase_date"),
            purchases_table.c.projectName.label("purchase_project_name"),
            reimbursements_table.c.name.label("reimbursement_name"),
            reimbursements_table.c.date.label("reimbursement_date"),
            reimbursements_table.c.projectName.label("reimbursement_project_name"),
            expenses_table.c.invoiceName.label("expense_invoiceName"),
            expenses_table.c.date.label("expense_date"),
            expenses_table.c.description.label("expense_description"),
            suppliers_table.c.name.label("purchase_account_name"),
            expense_opponents_table.c.name.label("expense_account_name"),
            reimbursements_table.c.bankAccountName.label("reimbursement_account_name")
        ]
        
        #Base query
        query = select(
            *select_columns
        ).select_from(
            payments_outgoing_table
        ).outerjoin(
            purchases_table, payments_outgoing_table.c.purchaseID == purchases_table.c.id,
        ).outerjoin(
            suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id    
        ).outerjoin(
            reimbursements_table, payments_outgoing_table.c.reimbursementID == reimbursements_table.c.id
        ).outerjoin(
            expenses_table, payments_outgoing_table.c.expenseID == expenses_table.c.id
        ).outerjoin(
            expense_opponents_table, expenses_table.c.opponentID == expense_opponents_table.c.id    
        ).where(
            payments_outgoing_table.c.bankAccountID == bankAccountID,
            payments_outgoing_table.c.date >= startDate,
            payments_outgoing_table.c.date <= endDate,
            payments_outgoing_table.c.isDelete == False
        ).limit(
            pageSize
        ).offset(
            (page - 1) * pageSize
        ).order_by(payments_outgoing_table.c.date.asc())
        
        payments = await database.fetch_all(query)
            
        return {
            "data": [
                {
                    "id": payment.id,
                    "date": payment.date,
                    "amount": payment.amount,
                    "purchaseID": payment.purchaseID,
                    "expenseID": payment.expenseID,
                    "reimbursementID": payment.reimbursementID,
                    "bankAccountID": payment.bankAccountID,
                    "isApprove": payment.isApprove,
                    "isDelete": payment.isDelete,
                    "createdAt": payment.createdAt,
                    "createdBy": payment.createdBy,
                    "updatedAt": payment.updatedAt,
                    "updatedBy": payment.updatedBy,
                    "status": payment.status,
                    "purchase": None if payment.purchaseID is None else  {
                        "date": payment.purchase_date,
                        "invoiceName": payment.purchase_invoiceName,
                        "accountName": payment.purchase_account_name,
                        "projectName": payment.purchase_project_name
                    },
                    "reimbursement": None if payment.reimbursementID is None else {
                        "date": payment.reimbursement_date,
                        "name": payment.reimbursement_name,
                        "accountName": payment.reimbursement_account_name,
                        "projectName": payment.reimbursement_project_name,
                        "bankName": payment.reimbursement_bank_name
                    },
                    "expense": None if payment.expenseID is None else {
                        "date": payment.expense_date,
                        "invoiceName": payment.expense_invoiceName,
                        "accountName": payment.expense_account_name,
                        "description": payment.expense_description,
                        "bankName": payment.expense_bank_name
                    }
                } for payment in payments
            ]
        }

    @staticmethod
    async def get_payment_by_date(date: d):
        select_columns = [
            payments_outgoing_table,  # Selects all columns from interpayment_table
            purchases_table.c.invoiceName.label("purchase_invoiceName"),
            purchases_table.c.date.label("purchase_date"),
            purchases_table.c.projectName.label("purchase_project_name"),
            reimbursements_table.c.name.label("reimbursement_name"),
            reimbursements_table.c.date.label("reimbursement_date"),
            reimbursements_table.c.projectName.label("reimbursement_project_name"),
            expenses_table.c.invoiceName.label("expense_invoiceName"),
            expenses_table.c.date.label("expense_date"),
            expenses_table.c.description.label("expense_description"),
            suppliers_table.c.name.label("purchase_account_name"),
            expense_opponents_table.c.name.label("expense_account_name"),
            reimbursements_table.c.bankAccountName.label("reimbursement_account_name")
        ]
        
        #Base query
        query = select(
            *select_columns
        ).select_from(
            payments_outgoing_table
        ).outerjoin(
            purchases_table, payments_outgoing_table.c.purchaseID == purchases_table.c.id,
        ).outerjoin(
            suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id    
        ).outerjoin(
            reimbursements_table, payments_outgoing_table.c.reimbursementID == reimbursements_table.c.id
        ).outerjoin(
            expenses_table, payments_outgoing_table.c.expenseID == expenses_table.c.id
        ).outerjoin(
            expense_opponents_table, expenses_table.c.opponentID == expense_opponents_table.c.id    
        ).where(
            payments_outgoing_table.c.date == d,
            payments_outgoing_table.c.isDelete == False
        )
        
        payments = await database.fetch_all(query)
            
        return {
            "data": [
                {
                    "id": payment.id,
                    "date": payment.date,
                    "amount": payment.amount,
                    "purchaseID": payment.purchaseID,
                    "expenseID": payment.expenseID,
                    "reimbursementID": payment.reimbursementID,
                    "bankAccountID": payment.bankAccountID,
                    "isApprove": payment.isApprove,
                    "isDelete": payment.isDelete,
                    "createdAt": payment.createdAt,
                    "createdBy": payment.createdBy,
                    "updatedAt": payment.updatedAt,
                    "updatedBy": payment.updatedBy,
                    "status": payment.status,
                    "purchase": None if payment.purchaseID is None else  {
                        "date": payment.purchase_date,
                        "invoiceName": payment.purchase_invoiceName,
                        "accountName": payment.purchase_account_name,
                        "projectName": payment.purchase_project_name
                    },
                    "reimbursement": None if payment.reimbursementID is None else {
                        "date": payment.reimbursement_date,
                        "name": payment.reimbursement_name,
                        "accountName": payment.reimbursement_account_name,
                        "projectName": payment.reimbursement_project_name
                    },
                    "expense": None if payment.expenseID is None else {
                        "date": payment.expense_date,
                        "invoiceName": payment.expense_invoiceName,
                        "accountName": payment.expense_account_name,
                        "description": payment.expense_description
                    }
                } for payment in payments
            ]
        }

    @staticmethod
    async def get_payment_by_id(id: int):
        """
        Get a payment by ID.
        
        Args:
            id (int): The ID of the payment.
        
        Returns:
            dict: The payment details or an error message if not found.
        """
        #Also select the bankName, bankAccountName, and bankAccountNumber from the bankAccounts table
        log_info(f"Retrieving payment with ID: {id}")
        query = select(
            payments_outgoing_table
        ).where(
            payments_outgoing_table.c.id == id,
        )
            
        try:
            payment = await database.fetch_one(query)
        
            if not payment:
                log_info(f"No payment found with ID: {id}")
                return {"error": "Payment not found", "status": 404}
            
            return PaymentOutgoing(
                id=payment.id,
                date=payment.date,
                amount=payment.amount,
                purchaseID=payment.purchaseID,
                expenseID=payment.expenseID,
                reimbursementID=payment.reimbursementID,
                salarySlipID=payment.salarySlipID,
                bankAccountID=payment.bankAccountID,
                isApprove=payment.isApprove,
                isDelete=payment.isDelete,
                createdAt=payment.createdAt,
                createdBy=payment.createdBy,
                updatedAt=payment.updatedAt,
                updatedBy=payment.updatedBy,
                status=payment.status,
            )
        except Exception as e:
            log_error(f"Error retrieving payment by ID {id}: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_payments_by_ids(payment_ids: List[int]):
        """
        Get payments by a list of IDs.
        
        Args:
            payment_ids (List[int]): A list of payment IDs.
        
        Returns:
            list: A list of payments associated with the IDs.
        """
        log_info(f"Retrieving payments with IDs: {payment_ids}")
        query = select(payments_outgoing_table).where(
            payments_outgoing_table.c.id.in_(payment_ids),
            payments_outgoing_table.c.isDelete == False
        )
        
        payments = await database.fetch_all(query)
        
        return [PaymentOutgoing(**payment) for payment in payments]

    @staticmethod
    async def get_payments_by_purchase_id(purchaseID: int):
        """
        Get all payments associated with a specific purchase ID.
        
        Args:
            purchaseID (int): The ID of the purchase.
        
        Returns:
            list: A list of payments associated with the purchase.
        """
        log_info(f"Retrieving payments for purchase ID: {purchaseID}")
        select_columns = [
            payments_outgoing_table,  # Selects all columns from interpayment_table
            bank_accounts_table.c.bankAccountName.label("bankAccountName"),
            bank_accounts_table.c.bankAccountNumber.label("bankAccountNumber"),
            bank_accounts_table.c.bankName.label("bankName")
        ]
        query = select(
            *select_columns
        ).select_from(
            payments_outgoing_table
        ).outerjoin(
            bank_accounts_table, payments_outgoing_table.c.bankAccountID == bank_accounts_table.c.id
        ).where(
            payments_outgoing_table.c.purchaseID == purchaseID,
            payments_outgoing_table.c.isDelete == False
        )
        
        payments = await database.fetch_all(query)
            
        return payments

    @staticmethod
    async def get_payments_by_reimbursement_id(reimbursementID: int):
        """
        Get all payments associated with a specific purchase ID.
        
        Args:
            purchaseID (int): The ID of the purchase.
        
        Returns:
            list: A list of payments associated with the purchase.
        """
        log_info(f"Retrieving payments for reimbursement ID: {reimbursementID}")
        select_columns = [
            payments_outgoing_table,  # Selects all columns from interpayment_table
            bank_accounts_table.c.bankAccountName.label("bankAccountName"),
            bank_accounts_table.c.bankAccountNumber.label("bankAccountNumber"),
            bank_accounts_table.c.bankName.label("bankName")
        ]
        query = select(
            *select_columns
        ).select_from(
            payments_outgoing_table
        ).outerjoin(
            bank_accounts_table, payments_outgoing_table.c.bankAccountID == bank_accounts_table.c.id
        ).where(
            payments_outgoing_table.c.reimbursementID == reimbursementID,
            payments_outgoing_table.c.isDelete == False
        )
        
        payments = await database.fetch_all(query)
            
        return payments
    
    @staticmethod
    async def get_payments_by_expense_id(expenseID: int):
        """
        Get all payments associated with a specific purchase ID.
        
        Args:
            expenseID (int): The ID of the expense.
        
        Returns:
            list: A list of payments associated with the purchase.
        """
        log_info(f"Retrieving payments for expense ID: {expenseID}")
        select_columns = [
            payments_outgoing_table,  # Selects all columns from interpayment_table
            bank_accounts_table.c.bankAccountName.label("bankAccountName"),
            bank_accounts_table.c.bankAccountNumber.label("bankAccountNumber"),
            bank_accounts_table.c.bankName.label("bankName")
        ]
        query = select(
            *select_columns
        ).select_from(
            payments_outgoing_table
        ).outerjoin(
            bank_accounts_table, payments_outgoing_table.c.bankAccountID == bank_accounts_table.c.id
        ).where(
            payments_outgoing_table.c.expenseID == expenseID,
            payments_outgoing_table.c.isDelete == False
        )
        
        payments = await database.fetch_all(query)
            
        return payments
        
        return [PaymentOutgoing(**payment) for payment in payments]
    
    @staticmethod
    async def get_payments_by_salary_slip_id(salarySlipID: int):
        """
        Get all payments associated with a specific salary slip ID.
        
        Args:
            salarySlipID (int): The ID of the salary slip.
        
        Returns:
            list: A list of payments associated with the salary slip.
        """
        log_info(f"Retrieving payments for salary slip ID: {salarySlipID}")
        query = select(payments_outgoing_table).where(
            payments_outgoing_table.c.salarySlipID == salarySlipID,
            payments_outgoing_table.c.isDelete == False
        )
        
        payments = await database.fetch_all(query)
        
        return [PaymentOutgoing(**payment) for payment in payments]

    @staticmethod
    async def get_payments_by_loan_id(loanID: int):
        """
        Get all payments associated with a specific loan ID.
        
        Args:
            loanID (int): The ID of the loan.
        
        Returns:
            list: A list of payments associated with the loan.
        """
        log_info(f"Retrieving payments for loan ID: {loanID}")
        query = select(payments_outgoing_table).where(
            payments_outgoing_table.c.loanID == loanID,
            payments_outgoing_table.c.isDelete == False
        )
        
        payments = await database.fetch_all(query)
        
        return [PaymentOutgoing(**payment) for payment in payments]

    @staticmethod
    async def update_status(paymentID: int, userID: int, status: str):
        """
        Update the status of a payment.
        
        Args:
            paymentID (int): The ID of the payment to update.
            userID (int): The ID of the user performing the update.
            status (str): The new status of the payment.
        
        Returns:
            dict: A success message or an error message if the update fails.
        """
        log_info(f"Updating payment status for ID: {paymentID} to {status}")
        
        current_time = dt.now()

        update_values = {
            "isApprove": status == "approve",
            "isDelete": status == "reject",
            "updatedBy": userID,
            "updatedAt": current_time,
        }
        query = (
            payments_outgoing_table.update()
            .where(payments_outgoing_table.c.id == paymentID)
            .values(**update_values)
        )
        
        try:
            # Keadaan sebelum & sesudah dibandingkan agar nilai lama ikut
            # terekam; tanpa ini audit hanya tahu "diubah", bukan "dari apa".
            _sebelum = await database.fetch_one(
                select(payments_outgoing_table).where(payments_outgoing_table.c.id == paymentID)
            )
            result = await database.execute(query)
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="payment_outgoing",
                entityID=paymentID,
                action="update_status",
                userID=userID,
                changes=AuditLogRepository.diff(
                    dict(_sebelum) if _sebelum else {},
                    dict(
                        await database.fetch_one(
                            select(payments_outgoing_table).where(
                                payments_outgoing_table.c.id == paymentID
                            )
                        )
                        or {}
                    ),
                ),
            )
            
            return {"message": "Payment status updated successfully"}
        except Exception as e:
            log_error(f"Error updating payment status: {str(e)}")
            return {"error": str(e), "status": 500}
      
    @staticmethod
    async def update_bulk_status(payment_ids: List[int], status: str, userID: int):
        # Dibaca lebih dulu: setelah diperbarui, pembuat aslinya tetap sama
        # tetapi lebih murah membacanya sekali di sini daripada per dokumen.
        payments_awal = await PaymentOutgoingRepository.get_payments_by_ids(
            payment_ids
        )
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
            query = payments_outgoing_table.update().where(
                payments_outgoing_table.c.id.in_(payment_ids)
            ).values(
                isApprove=status == "approve",
                isDelete=status == "reject",
                updatedBy=userID,
                updatedAt=dt.now()
            )
            
            await database.execute(query)
            from repository.audit_log_repository import AuditLogRepository

            # Dicatat per pembayaran, bukan sekali untuk seluruh kumpulan:
            # riwayat dibaca per dokumen, sehingga satu catatan gabungan
            # tidak akan muncul di detail pembayaran mana pun.
            # Persetujuan atas dokumen sendiri ditandai tersendiri.
            #
            # Hal itu hanya mungkin dilakukan pemilik usaha, dan memang
            # diizinkan — tetapi harus terbaca sebagai keadaan yang berbeda
            # saat riwayat ditelusuri, bukan tenggelam di antara persetujuan
            # biasa.
            # `get_payments_by_ids` mengembalikan objek PaymentOutgoing,
            # bukan baris basis data — nilainya dibaca lewat atribut, bukan
            # kunci. Memakai p["id"] di sini melempar TypeError dan seluruh
            # persetujuan gagal.
            pembuat = {
                p.id: getattr(p, "createdBy", None) for p in (payments_awal or [])
            }

            for _pid in payment_ids:
                perubahan = {"status": {"from": None, "to": status}}
                if status == "approve" and pembuat.get(_pid) == userID:
                    perubahan["selfApproved"] = True

                await AuditLogRepository.record(
                    entity="payment_outgoing",
                    entityID=_pid,
                    action="update_status",
                    userID=userID,
                    changes=perubahan,
                )

            return {"message": "Status updated successfully"}
        except Exception as e:
            log_error(f"Error updating status for payments with IDs {payment_ids}: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def move_payment(id: int, date: d, userID: int):
        log_info(f"Moving payment with ID: {id} to date: {date}")
        query = payments_outgoing_table.update().where(
            payments_outgoing_table.c.id == id
        ).values(
            date=date,
            updatedAt=dt.now(),
            updatedBy=userID
        )
        
        try:
            await database.execute(query)
            return {"message": "Payment moved successfully"}
        except Exception as e:
            log_error(f"Error moving payment: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def delete_payment_by_purchase_id(purchaseID: int, userID: int):
        """
        Delete all payments associated with a specific purchase ID.
        
        Args:
            purchaseID (int): The ID of the purchase.
        
        Returns:
            dict: A success message or an error message if the deletion fails.
        """
        log_info(f"Deleting payments for purchase ID: {purchaseID}")
        query = payments_outgoing_table.update().where(
            payments_outgoing_table.c.purchaseID == purchaseID
        ).values(
            isDelete=True,
            isApprove=False,
            updatedAt=dt.now(),
            updatedBy=userID
        )
        
        try:
            await database.execute(query)
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="payment_outgoing",
                entityID=purchaseID,
                action="delete",
                userID=userID,
            )

            return {"message": "Payments deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting payments for purchase ID {purchaseID}: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_calendar_data(month: int, year: int, bankAccounts: List[int]):
        try:
            if month < 1 or month > 12:
                return {"error": "Invalid month. Month must be between 1 and 12.", "status": 400}
            if year < 2020:
                return {"error": "Invalid year. Year must be 2020 or later.", "status": 400}
            
            if(bankAccounts is not None and len(bankAccounts) > 0):
                query = select(
                    func.sum(payments_outgoing_table.c.amount).label("amount"),
                    payments_outgoing_table.c.date
                ).where(
                    payments_outgoing_table.c.date >= _month_start(month, year),
                    payments_outgoing_table.c.date < _month_end(month, year),
                    payments_outgoing_table.c.isDelete == False,
                    payments_outgoing_table.c.bankAccountID.in_(bankAccounts)
                ).group_by(
                    payments_outgoing_table.c.date
                )
            else:
                # If no bank accounts are provided, fetch all payments for the specified month and year
                query = select(
                    func.sum(payments_outgoing_table.c.amount).label("amount"),
                    payments_outgoing_table.c.date
                ).where(
                    payments_outgoing_table.c.date >= _month_start(month, year),
                    payments_outgoing_table.c.date < _month_end(month, year),
                    payments_outgoing_table.c.isDelete == False
                ).group_by(
                    payments_outgoing_table.c.date
                )
                
            payments = await database.fetch_all(query)
            return [
                {   
                    "date": payment.date,
                    "amount": payment.amount
                } for payment in payments
            ]
        except Exception as e:
            log_error(f"Error retrieving calendar data: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def download_calendar_data(month: int, year: int, bankAccounts: List[int]):
        """
        Get all payments with pagination, filtering, and sorting.
        
        Args:
            page (int): The page number for pagination.
            pageSize (int): The number of items per page.
            filterObject (dict): The filter criteria for the payments.
            sortBy (str): The field to sort by.
            sortByDirection (str): The direction of sorting ('asc' or 'desc').
            keyword (str | None): A keyword to search in the payments.
        
        Returns:
            dict: A dictionary containing the payments and pagination info.
        """
        # Placeholder for actual implementation
        # SELECT payments.*, COALESCE(purchases.invoiceName, reimbursements.name) AS documetName

        or_conditions = []
        or_conditions.append(payments_outgoing_table.c.isApprove == True)
        or_conditions.append(
            and_(
                payments_outgoing_table.c.isApprove == False,
                payments_outgoing_table.c.isDelete == False
                )
            )

        month_names = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }

        month_case = case(
            *( (salary_slips_table.c.month == num, name) for num, name in month_names.items() ),
            else_=literal('Unknown')
        )
        
        query = select(
            payments_outgoing_table,
            func.coalesce(
                purchases_table.c.invoiceName, 
                reimbursements_table.c.name,
                func.concat(
                    literal('Salary '),
                    employees_table.c.name,
                    literal(' '),
                    month_case,
                    literal(' '),
                    salary_slips_table.c.year.cast(String)
                ), 
                expenses_table.c.invoiceName
            ).label("documentName"),
            func.coalesce(
                suppliers_table.c.name, 
                reimbursements_table.c.bankAccountName,
                employees_table.c.name,
                expense_opponents_table.c.name
            ).label("opponent"),
            func.coalesce(
                purchases_table.c.date, 
                reimbursements_table.c.date,
                salary_slips_table.c.createdAt,
                expenses_table.c.date
            ).label("documentDate"),
            bank_accounts_table.c.bankAccountName.label("bankAccountName"),
            bank_accounts_table.c.bankAccountNumber.label("bankAccountNumber"),
            bank_accounts_table.c.bankName.label("bankName")
        ).outerjoin(
            purchases_table, payments_outgoing_table.c.purchaseID == purchases_table.c.id
        ).outerjoin(
            suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id
        ).outerjoin(
            reimbursements_table, payments_outgoing_table.c.reimbursementID == reimbursements_table.c.id
        ).outerjoin(
            salary_slips_table, payments_outgoing_table.c.salarySlipID == salary_slips_table.c.id
        ).outerjoin(
            employees_table, salary_slips_table.c.userID == employees_table.c.id
        ).outerjoin(
            expenses_table, payments_outgoing_table.c.expenseID == expenses_table.c.id
        ).outerjoin(
            expense_opponents_table, expenses_table.c.opponentID == expense_opponents_table.c.id
        ).outerjoin(
            bank_accounts_table, payments_outgoing_table.c.bankAccountID == bank_accounts_table.c.id
        )
        
        # ===== WHERE CONDITIONS =====
        conditions = [
            or_(*or_conditions),
            payments_outgoing_table.c.date >= _month_start(month, year),
            payments_outgoing_table.c.date < _month_end(month, year),
        ]

        # Tambahkan filter bankAccount hanya kalau ada isinya
        if bankAccounts:
            conditions.append(
                payments_outgoing_table.c.bankAccountID.in_(bankAccounts)
            )

        query = query.where(and_(*conditions))
    
        result = await database.fetch_all(query)
        return result
    @staticmethod
    async def get_calendar_data_by_date(date: int, month: int, year: int, bankAccounts: List[int]):
        try:
            if month < 1 or month > 12:
                return {"error": "Invalid month. Month must be between 1 and 12.", "status": 400}
            if year < 2020:
                return {"error": "Invalid year. Year must be 2020 or later.", "status": 400}
            
            select_columns = [
                payments_outgoing_table,  # Selects all columns from interpayment_table
                purchases_table.c.invoiceName.label("purchase_invoiceName"),
                purchases_table.c.date.label("purchase_date"),
                purchases_table.c.projectName.label("purchase_project_name"),
                purchases_table.c.purchaseOrderName.label("purchase_purchase_order_name"),
                reimbursements_table.c.name.label("reimbursement_name"),
                reimbursements_table.c.date.label("reimbursement_date"),
                reimbursements_table.c.projectName.label("reimbursement_project_name"),
                expenses_table.c.invoiceName.label("expense_invoiceName"),
                expenses_table.c.date.label("expense_date"),
                expenses_table.c.description.label("expense_description"),
                suppliers_table.c.name.label("purchase_account_name"),
                expense_opponents_table.c.name.label("expense_account_name"),
                reimbursements_table.c.bankAccountName.label("reimbursement_account_name"),
                salary_slips_table.c.month.label("salary_slip_month"),
                salary_slips_table.c.year.label("salary_slips_year"),
                employees_table.c.name.label("salary_slip_name"),
                loans_table.c.creditorName.label("loan_creditor_name"),
                loans_table.c.description.label("loan_description"),
                # destination bank of each document -> used to estimate
                # inter-bank transfer fees on the calendar day view
                purchases_table.c.bankName.label("purchase_bank_name"),
                expenses_table.c.bankName.label("expense_bank_name"),
                reimbursements_table.c.bankName.label("reimbursement_bank_name"),
                salary_slips_table.c.bankName.label("salary_slip_bank_name"),
                loans_table.c.bankName.label("loan_bank_name")
            ]
            
            #Base query
            query = select(
                *select_columns
            ).select_from(
                payments_outgoing_table
            ).outerjoin(
                purchases_table, payments_outgoing_table.c.purchaseID == purchases_table.c.id,
            ).outerjoin(
                suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id    
            ).outerjoin(
                reimbursements_table, payments_outgoing_table.c.reimbursementID == reimbursements_table.c.id
            ).outerjoin(
                expenses_table, payments_outgoing_table.c.expenseID == expenses_table.c.id
            ).outerjoin(
                expense_opponents_table, expenses_table.c.opponentID == expense_opponents_table.c.id    
            ).outerjoin(
                salary_slips_table, payments_outgoing_table.c.salarySlipID == salary_slips_table.c.id    
            ).outerjoin(
                employees_table, salary_slips_table.c.userID == employees_table.c.id    
            ).outerjoin(
                loans_table, payments_outgoing_table.c.loanID == loans_table.c.id    
            ).where(
                payments_outgoing_table.c.date >= _day_start(date, month, year),
                payments_outgoing_table.c.date < _day_end(date, month, year),
                payments_outgoing_table.c.isDelete == False
            )
            
            if bankAccounts is not None:
                query = query.where(payments_outgoing_table.c.bankAccountID.in_(bankAccounts))
            
            payments = await database.fetch_all(query)
                
            return [
                {
                    "id": payment.id,
                    "date": payment.date,
                    "amount": payment.amount,
                    "purchaseID": payment.purchaseID,
                    "expenseID": payment.expenseID,
                    "reimbursementID": payment.reimbursementID,
                    "salarySlipID": payment.salarySlipID,
                    "loanID": payment.loanID,
                    "bankAccountID": payment.bankAccountID,
                    "isApprove": payment.isApprove,
                    "isDelete": payment.isDelete,
                    "createdAt": payment.createdAt,
                    "createdBy": payment.createdBy,
                    "updatedAt": payment.updatedAt,
                    "updatedBy": payment.updatedBy,
                    "status": payment.status,
                    "purchase": None if payment.purchaseID is None else  {
                        "date": payment.purchase_date,
                        "invoiceName": payment.purchase_invoiceName,
                        "accountName": payment.purchase_account_name,
                        "projectName": payment.purchase_project_name,
                        "purchaseOrderName": payment.purchase_purchase_order_name,
                        "bankName": payment.purchase_bank_name,
                    },
                    "reimbursement": None if payment.reimbursementID is None else {
                        "date": payment.reimbursement_date,
                        "name": payment.reimbursement_name,
                        "accountName": payment.reimbursement_account_name,
                        "projectName": payment.reimbursement_project_name
                    },
                    "expense": None if payment.expenseID is None else {
                        "date": payment.expense_date,
                        "invoiceName": payment.expense_invoiceName,
                        "accountName": payment.expense_account_name,
                        "description": payment.expense_description
                    },
                    "salarySlip": None if payment.salarySlipID is None else {
                        "month": payment.salary_slip_month,
                        "year": payment.salary_slips_year,
                        "name": payment.salary_slip_name,
                        "bankName": payment.salary_slip_bank_name
                    },
                    "loan": None if payment.loanID is None else {
                        "creditorName": payment.loan_creditor_name,
                        "description": payment.loan_description,
                        "bankName": payment.loan_bank_name
                    },
                    # flattened destination bank, whichever document this
                    # payment belongs to (used for transfer-fee estimation)
                    "destinationBankName": (
                        payment.purchase_bank_name
                        or payment.expense_bank_name
                        or payment.reimbursement_bank_name
                        or payment.salary_slip_bank_name
                        or payment.loan_bank_name
                    )
                } for payment in payments
            ]
        except Exception as e:
            log_error(f"Error retrieving payment outgoing calendar data: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_calendar_selector_data_by_date(date: int, month: int, year: int, bankAccounts: List[int]):
        try:
            if month < 1 or month > 12:
                return {"error": "Invalid month. Month must be between 1 and 12.", "status": 400}
            if year < 2020:
                return {"error": "Invalid year. Year must be 2020 or later.", "status": 400}
            
            total_query = select(func.count()).select_from(payments_outgoing_table).where(
                payments_outgoing_table.c.date >= _day_start(date, month, year),
                payments_outgoing_table.c.date < _day_end(date, month, year),
                payments_outgoing_table.c.isDelete == False
            ).group_by(payments_outgoing_table.c.bankAccountID)
            
            total = await database.fetch_val(total_query)
            return total
        except Exception as e:
            log_error(f"Error retrieving payment outgoing calendar data: {str(e)}")
            return {"error": str(e), "status": 500}


    @staticmethod
    async def get_purchase_pph_report(month: int, year: int):
        try:
            supplier_columns = [
                payments_outgoing_table.c.date.label("payment_date"),
                payments_outgoing_table.c.amount.label("amount"),
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
                suppliers_table.c.npwp.label("supplier_npwp")
            ]

            # Alias for payments_outgoing_table to use in subquery
            po_alias = payments_outgoing_table.alias("po_alias")

            # Create a datetime object for the first day of the month
            first_day_of_month = dt(year, month, 1)

            # Subquery to sum previous payments for the same purchase before current payment date
            previous_amount_subquery = (
                select(func.coalesce(func.sum(po_alias.c.amount), 0))
                .where(
                    and_(
                        po_alias.c.purchaseID == payments_outgoing_table.c.purchaseID,
                        po_alias.c.date < first_day_of_month,
                        po_alias.c.isApprove == True
                    )
                )
                .correlate(payments_outgoing_table)
                .scalar_subquery()
            )
            
            conditions = [
                payments_outgoing_table.c.isApprove == True,
                purchases_table.c.isDelete == False,
                purchases_table.c.pphCode != None,
                payments_outgoing_table.c.date >= _month_start(month, year),
                payments_outgoing_table.c.date < _month_end(month, year),
            ]

            order_by = payments_outgoing_table.c.date.asc()
            
            query = (
                select(
                    *purchases_table.c,
                    *supplier_columns,
                    previous_amount_subquery.label("previous_amount")
                )
                .join(purchases_table, payments_outgoing_table.c.purchaseID == purchases_table.c.id)
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .where(*conditions)
                .order_by(order_by)
            )
            purchases = await database.fetch_all(query)

            if not purchases:
                return []

            # Convert the result to a list of dictionaries
            purchase_list = [dict(purchase) for purchase in purchases]
            return purchase_list
        except Exception as e:
            log_error(f"Error fetching PPN report: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_expense_pph_report(month: int, year: int):
        try:
            opponent_columns = [
                payments_outgoing_table.c.date.label("payment_date"),
                payments_outgoing_table.c.amount.label("amount"),
                expense_opponents_table.c.id.label("opponent_id"),
                expense_opponents_table.c.name.label("opponent_name"),
                expense_opponents_table.c.npwp.label("opponent_npwp")
            ]

            # Alias for payments_outgoing_table to use in subquery
            po_alias = payments_outgoing_table.alias("po_alias")

            # Create a datetime object for the first day of the month
            first_day_of_month = dt(year, month, 1)

            # Subquery to sum previous payments for the same purchase before current payment date
            previous_amount_subquery = (
                select(func.coalesce(func.sum(po_alias.c.amount), 0))
                .where(
                    and_(
                        po_alias.c.expenseID == payments_outgoing_table.c.expenseID,
                        po_alias.c.date < first_day_of_month,
                        po_alias.c.isApprove == True
                    )
                )
                .correlate(payments_outgoing_table)
                .scalar_subquery()
            )
            
            conditions = [
                payments_outgoing_table.c.isApprove == True,
                expenses_table.c.isDelete == False,
                expenses_table.c.pphCode != None,
                payments_outgoing_table.c.date >= _month_start(month, year),
                payments_outgoing_table.c.date < _month_end(month, year),
            ]

            order_by = payments_outgoing_table.c.date.asc()
            
            query = (
                select(
                    *expenses_table.c,
                    *opponent_columns,
                    previous_amount_subquery.label("previous_amount")
                )
                .join(expenses_table, payments_outgoing_table.c.expenseID == expenses_table.c.id)
                .join(expense_opponents_table, expenses_table.c.opponentID == expense_opponents_table.c.id)
                .where(*conditions)
                .order_by(order_by)
            )
            purchases = await database.fetch_all(query)

            if not purchases:
                return []

            # Convert the result to a list of dictionaries
            purchase_list = [dict(purchase) for purchase in purchases]
            return purchase_list
        except Exception as e:
            log_error(f"Error fetching purchase report by project: {str(e)}")
            return {"error": str(e), "status": 500}