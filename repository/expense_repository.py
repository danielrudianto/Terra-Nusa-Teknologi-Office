from sqlalchemy import select, func, or_, insert, update
from utils.permission import boleh_menyetujui_sendiri
from utils.errors import ErrorCode, app_error, internal_error
from utils.database import database
from utils.logger_utils import log_error
from models.expense_model import expenses_table
from models.expense_opponent_model import expense_opponents_table
from datetime import datetime as dt

class ExpenseRepository:
    @staticmethod
    async def get_ppn_report(month: int, year: int):
        """
        Beban ber-PPN pada satu periode.

        Bentuk keluarannya DISAMAKAN dengan laporan PPN pembelian, karena
        keduanya digabung menjadi satu rekap. Beban tidak punya pemasok
        melainkan lawan transaksi — yang dipakai rekap hanya nama dan NPWP,
        sisanya dikosongkan agar bentuknya tetap sama.

        `ppn` tersimpan sebagai PERSEN, sama seperti pada pembelian; rekap
        yang menghitung ulang nilainya berlaku untuk keduanya.
        """
        try:
            opponent_columns = [
                expense_opponents_table.c.id.label("opponent_id"),
                expense_opponents_table.c.name.label("opponent_name"),
                expense_opponents_table.c.npwp.label("opponent_npwp"),
            ]

            conditions = [
                expenses_table.c.isDelete == False,
                expenses_table.c.ppn > 0,
                func.extract("month", expenses_table.c.date) == month,
                func.extract("year", expenses_table.c.date) == year,
            ]

            query = (
                select(*expenses_table.c, *opponent_columns)
                # Kiri luar: lawan transaksi tidak wajib diisi pada beban,
                # dan beban ber-PPN tanpa lawan transaksi tetap harus masuk
                # rekap — pajaknya tetap terutang.
                .select_from(
                    expenses_table.outerjoin(
                        expense_opponents_table,
                        expenses_table.c.opponentID == expense_opponents_table.c.id,
                    )
                )
                .where(*conditions)
                .order_by(expenses_table.c.date.asc())
            )
            rows = await database.fetch_all(query)

            hasil = []
            for row in rows:
                d = dict(row)
                d["supplier"] = {
                    "id": d.get("opponent_id"),
                    "name": d.get("opponent_name") or "",
                    "address": "",
                    "city": "",
                    "province": "",
                    "prefix": "",
                    "npwp": d.get("opponent_npwp"),
                }
                for f in ("opponent_id", "opponent_name", "opponent_npwp"):
                    d.pop(f, None)
                # Penanda asal baris; rekap memisahkannya agar terlihat mana
                # yang dari pembelian dan mana dari beban.
                d["sumber"] = "expense"
                # `taxInvoiceName` ikut terbawa dari kolomnya; baris lama
                # yang belum mengisinya tetap aman karena kolomnya nullable.
                hasil.append(d)
            return hasil
        except Exception as e:
            log_error(f"Error fetching expense PPN report: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_ppn_masukan_kreditable_bulanan(until_year: int, until_month: int):
        """
        Total PPN masukan beban yang DAPAT dikreditkan, per bulan.

        Sama seperti pembelian: hanya beban ber-PPN yang sudah punya nomor
        faktur pajak. Dipakai laporan posisi PPN untuk kompensasi antar masa.
        """
        try:
            from datetime import datetime as _dt

            end_date = (
                _dt(until_year + 1, 1, 1)
                if until_month == 12
                else _dt(until_year, until_month + 1, 1)
            )
            e = expenses_table.c
            y = func.extract("year", e.date)
            m = func.extract("month", e.date)
            query = (
                select(
                    y.label("y"),
                    m.label("m"),
                    func.coalesce(func.sum(e.dpp * e.ppn / 100), 0).label("total"),
                )
                .where(
                    e.isDelete == False,
                    e.ppn > 0,
                    e.taxInvoiceName.isnot(None),
                    func.trim(e.taxInvoiceName) != "",
                    e.date < end_date,
                )
                .group_by(y, m)
            )
            rows = await database.fetch_all(query)
            return {(int(r["y"]), int(r["m"])): float(r["total"] or 0) for r in rows}
        except Exception as e:
            log_error(f"Error fetching monthly creditable PPN (expense): {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def create(expense_data: dict):
        """
        Create an expense in the database.
        """
        try:
            query = insert(expenses_table).values(expense_data)
            expense_id = await database.execute(query)
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="expenses",
                entityID=expense_id,
                action="create",
            )
            return expense_id
        except Exception as e:
            log_error(f"Error creating expense: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_all(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None, start: dt, end: dt, ignore: bool):
        """
        Retrieve a list of expenses from the database.
        """
        if page < 0:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            offset = page * pageSize

            opponent_columns = [
                expense_opponents_table.c.id.label("opponentID"),
                expense_opponents_table.c.name.label("opponentName")
            ]

            conditions = [expenses_table.c.isDelete == False]
            
            if not ignore:
                conditions.append(expenses_table.c.date >= start)
                conditions.append(expenses_table.c.date <= end)

            or_conditions = []
            if keyword is not None and keyword != "":
                or_conditions.append(expenses_table.c.invoiceName.ilike(f"%{keyword}%"))
                or_conditions.append(expenses_table.c.receiptName.ilike(f"%{keyword}%"))
                # Panduan menyebut faktur pajak sebagai kolom yang dicari;
                # tanpa baris ini janji itu tidak pernah berlaku.
                or_conditions.append(expenses_table.c.taxInvoiceName.ilike(f"%{keyword}%"))
                or_conditions.append(expenses_table.c.description.ilike(f"%{keyword}%"))
                or_conditions.append(expense_opponents_table.c.name.ilike(f"%{keyword}%"))
                or_conditions.append(expense_opponents_table.c.description.ilike(f"%{keyword}%"))
            
            if or_conditions:
                conditions.append(or_(*or_conditions))

            # Filter conditions
            filter_or_conditions = []
            if filterObject.get("isDue"):
                filter_or_conditions.append(expenses_table.c.dueDate <= dt.now().date())
            if filterObject.get("isNotDue"):
                filter_or_conditions.append(expenses_table.c.dueDate > dt.now().date())
            
            if filter_or_conditions:
                conditions.append(or_(*filter_or_conditions))

            payment_or_conditions = []
            if filterObject.get("isPaid"):
                payment_or_conditions.append(expenses_table.c.isPaid == True)
            if filterObject.get("isUnpaid"):
                payment_or_conditions.append(expenses_table.c.isPaid == False)
            
            if payment_or_conditions:
                conditions.append(or_(*payment_or_conditions))

            # Sort by
            if sortBy == "date":
                order_by = expenses_table.c.date.desc() if sortByDirection == "desc" else expenses_table.c.date.asc()
            elif sortBy == "dueDate":
                order_by = expenses_table.c.dueDate.desc() if sortByDirection == "desc" else expenses_table.c.dueDate.asc()
            elif sortBy == "total":
                order_by = expenses_table.c.dpp.desc() if sortByDirection == "desc" else expenses_table.c.dpp.asc()
            elif sortBy == "invoiceName":
                order_by = expenses_table.c.invoiceName.desc() if sortByDirection == "desc" else expenses_table.c.invoiceName.asc()
            else:
                order_by = expenses_table.c.date.desc()
                
            query = (
                select(*expenses_table.c, *opponent_columns)
                .select_from(expenses_table.join(expense_opponents_table, expenses_table.c.opponentID == expense_opponents_table.c.id, isouter=True))
                .where(*conditions)
                .order_by(order_by)
                .offset(offset)
                .limit(pageSize)
            )
            expenses = await database.fetch_all(query)

            # Count the total number of expenses
            count_query = (
                select(func.count())
                .select_from(expenses_table.join(expense_opponents_table, expenses_table.c.opponentID == expense_opponents_table.c.id, isouter=True))
                .where(*conditions)
            )
            count = await database.fetch_val(count_query)

            # Convert the result
            expense_result = []
            for expense in expenses:
                expense_dict = dict(expense)
                expense_dict["opponent"] = {
                    "id": expense_dict["opponentID"],
                    "name": expense_dict["opponentName"],
                }
                # Remove the individual opponent fields
                del expense_dict["opponentID"]
                del expense_dict["opponentName"]
                expense_result.append(expense_dict)

            return {
                "data": expense_result,
                "count": count,
            }
        except Exception as e:
            log_error(f"Error fetching expenses: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_by_id(id: int):
        """
        Get an expense by ID.
        """
        try:
            expense_opponent_columns = [
                expense_opponents_table.c.id.label("expense_opponent_id"),
                expense_opponents_table.c.name.label("expense_opponent_name"),
                expense_opponents_table.c.type.label("expense_opponent_type"),
                expense_opponents_table.c.description.label("expense_opponent_description"),
                expense_opponents_table.c.paymentNumber.label("expense_opponent_payment_number"),
            ]
            query = (
                select(*expenses_table.c, *expense_opponent_columns)
                .join(expense_opponents_table, expenses_table.c.opponentID == expense_opponents_table.c.id)
                .where(expenses_table.c.id == id)
            )
            expense = await database.fetch_one(query)

            if not expense:
                return {"error": "Expense not found", "status": 404}

            return dict(expense)
        except Exception as e:
            log_error(f"Error fetching expense by ID: {str(e)}")
            return internal_error()

    @staticmethod
    async def approve_by_id(
        id: int, userID: int, user_level: int | None = None
    ):
        """
        Update expense status to approved.
        """
        try:
            # Yang membuat dokumen tidak boleh menyetujuinya sendiri.
            #
            # Dikecualikan untuk level 4 ke atas: keduanya memang berwenang
            # atas seluruh dokumen, dan kerap merekalah satu-satunya yang
            # hadir untuk menyetujui. Pengecualian itu tetap tercatat pada
            # jejak aktivitas.
            if not boleh_menyetujui_sendiri(user_level):
                pembuat = await database.fetch_val(
                    select(expenses_table.c.createdBy).where(
                        expenses_table.c.id == id
                    )
                )
                if pembuat is not None and int(pembuat) == int(userID):
                    return app_error(
                        ErrorCode.SELF_APPROVAL_FORBIDDEN,
                        "Dokumen tidak dapat disetujui oleh pembuatnya "
                        "sendiri. Mintakan persetujuan kepada pengguna lain.",
                        403,
                    )

            query = (
                expenses_table.update()
                .where(expenses_table.c.id == id)
                .values(
                    isApprove=True,
                    approvedBy=userID,
                    approvedAt=dt.now()
                )
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Expense not found", "status": 404}
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="expenses",
                # entityID adalah id biaya; userID adalah pelaku persetujuan.
            entityID=id,
                action="approve",
                userID=userID,
            )
            
            return {"message": "Expense approved successfully"}
        except Exception as e:
            log_error(f"Error approving expense: {str(e)}")
            return internal_error()

    @staticmethod
    async def update_payment_status(expenseID: int, isPaid: bool, userID: int):
        """
        Update the payment status of an expense.
        """
        try:
            # Keadaan sebelum & sesudah dibandingkan agar nilai lama ikut
            # terekam; tanpa ini audit hanya tahu "diubah", bukan "dari apa".
            _sebelum = await database.fetch_one(
                select(expenses_table).where(expenses_table.c.id == expenseID)
            )
            query = (
                expenses_table.update()
                .where(expenses_table.c.id == expenseID)
                .values(
                    isPaid=isPaid,
                    updatedBy=userID,
                    updatedAt=dt.now()
                )
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Expense not found", "status": 404}
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="expenses",
                entityID=expenseID,
                action="update_payment_status",
                userID=userID,
                changes=AuditLogRepository.diff(
                    dict(_sebelum) if _sebelum else {},
                    dict(
                        await database.fetch_one(
                            select(expenses_table).where(
                                expenses_table.c.id == expenseID
                            )
                        )
                        or {}
                    ),
                ),
            )

            return {"message": "Expense payment status updated successfully"}
        except Exception as e:
            log_error(f"Error updating expense payment status: {str(e)}")
            return internal_error()

    @staticmethod
    async def update(expense_id: int, expense_data: dict):
        """
        Update an expense in the database.
        """
        try:
            # Keadaan sebelum & sesudah dibandingkan agar nilai lama ikut
            # terekam; tanpa ini audit hanya tahu "diubah", bukan "dari apa".
            _sebelum = await database.fetch_one(
                select(expenses_table).where(expenses_table.c.id == expense_id)
            )
            query = (
                expenses_table.update()
                .where(expenses_table.c.id == expense_id)
                .values(expense_data)
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Expense not found", "status": 404}
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="expenses",
                entityID=expense_id,
                action="update",
                changes=AuditLogRepository.diff(
                    dict(_sebelum) if _sebelum else {},
                    dict(
                        await database.fetch_one(
                            select(expenses_table).where(
                                expenses_table.c.id == expense_id
                            )
                        )
                        or {}
                    ),
                ),
            )

            return {"message": "Expense updated successfully"}
        except Exception as e:
            log_error(f"Error updating expense: {str(e)}")
            return internal_error()

    @staticmethod
    async def delete(expense_id: int, user_id: int):
        """
        Soft delete an expense from the database.
        """
        try:
            query = (
                expenses_table.update()
                .where(expenses_table.c.id == expense_id)
                .values({
                    "isDelete": True,
                    "deletedBy": user_id,
                    "deletedAt": dt.now()
                })
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Expense not found", "status": 404}
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="expenses",
                entityID=expense_id,
                action="delete",
                userID=user_id,
            )

            return {"message": "Expense deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting expense: {str(e)}")
            return internal_error()