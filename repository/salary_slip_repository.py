from sqlalchemy import select, func, update
from utils.errors import ErrorCode, app_error
from utils.database import database
from utils.logger_utils import log_error
from models.salary_slip_model import salary_slips_table, salary_slips_allowance_table, salary_slips_deduction_table
from models.employee_model import employees_table
from datetime import datetime as dt

class SalarySlipRepository:
    @staticmethod
    async def validate(userID: int, month: int, year: int):
        query = salary_slips_table.select().where(
            (salary_slips_table.c.userID == userID) &
            (salary_slips_table.c.month == month) &
            (salary_slips_table.c.year == year) &
            (salary_slips_table.c.isDelete == False)
        )
        existing_slip = await database.fetch_one(query)
        if existing_slip:
            return app_error(ErrorCode.SALARY_SLIP_EXISTS, "Salary slip already exists for this user, month, and year.", 400)
        return {"message": "Validation successful."}

    @staticmethod
    async def create(salary_slip_data: dict):
        query = salary_slips_table.insert().values(salary_slip_data)
        try:
            result = await database.execute(query)
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="salary_slips",
                entityID=result,
                action="create",
            )
            return result
        except Exception as e:
            log_error(f"Error creating salary slip: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def fetch(
        page: int,
        pageSize: int,
        keyword: str,
        month: int,
        year: int,
        sortBy: str = None,
        sortByDirection: str = "asc",
    ):
        # Kolom yang boleh dipakai mengurutkan; daftar putih mencegah nama
        # kolom sembarang ikut masuk ke query.
        SORTABLE = {
            "name": employees_table.c.name,
            "basicSalary": salary_slips_table.c.basicSalary,
            "isPaid": salary_slips_table.c.isPaid,
            "department": salary_slips_table.c.department,
            "position": salary_slips_table.c.position,
        }
        if sortBy in SORTABLE:
            _kolom = SORTABLE[sortBy]
            _urut = [
                _kolom.desc()
                if str(sortByDirection).lower() == "desc"
                else _kolom.asc()
            ]
        else:
            # Bawaan: periode terbaru lebih dulu, lalu nama karyawan.
            _urut = [
                salary_slips_table.c.year.desc(),
                salary_slips_table.c.month.desc(),
                employees_table.c.name.asc(),
            ]

        allowance_subq = (
            select(
                salary_slips_allowance_table.c.salarySlipID,
                func.coalesce(func.sum(salary_slips_allowance_table.c.amount), 0).label("allowance")
            )
            .group_by(salary_slips_allowance_table.c.salarySlipID)
        ).subquery()

        deduction_subq = (
            select(
                salary_slips_deduction_table.c.salarySlipID,
                func.coalesce(func.sum(salary_slips_deduction_table.c.amount), 0).label("deduction")
            )
            .group_by(salary_slips_deduction_table.c.salarySlipID)
        ).subquery()
        
        query = select(
            salary_slips_table.c.id,
            salary_slips_table.c.userID,
            salary_slips_table.c.month,
            salary_slips_table.c.year,
            salary_slips_table.c.taxCategory,
            salary_slips_table.c.position,
            salary_slips_table.c.department,
            salary_slips_table.c.basicSalary,
            (salary_slips_table.c.transportationAllowanceRate * salary_slips_table.c.transportationAllowanceQuantity).label("transportation"),
            (salary_slips_table.c.mealAllowanceRate * salary_slips_table.c.mealAllowanceQuantity).label("meal"),
            (salary_slips_table.c.overtimeRate * salary_slips_table.c.overtimeQuantity).label("overtime"),
            allowance_subq.c.allowance,
            deduction_subq.c.deduction,
            salary_slips_table.c.taxAmount,
            salary_slips_table.c.isDelete,
            salary_slips_table.c.isPaid,
            employees_table.c.name,
        ).join(
            employees_table, salary_slips_table.c.userID == employees_table.c.id
        ).outerjoin(
            allowance_subq, salary_slips_table.c.id == allowance_subq.c.salarySlipID
        ).outerjoin(
            deduction_subq, salary_slips_table.c.id == deduction_subq.c.salarySlipID
        ).where(
            employees_table.c.name.ilike(f"%{keyword}%"),
            salary_slips_table.c.month == month,
            salary_slips_table.c.year == year
        ).order_by(*_urut).offset((page - 1) * pageSize).limit(pageSize)
        
        try:
            result = await database.fetch_all(query)
        
            countQuery = select(func.count()).select_from(
                salary_slips_table
            ).join(
                employees_table, salary_slips_table.c.userID == employees_table.c.id
            ).where(
                employees_table.c.name.ilike(f"%{keyword}%"),
                salary_slips_table.c.month == month,
                salary_slips_table.c.year == year
            )
            
            total_count = await database.fetch_val(countQuery)
            
            return {
                "data": [dict(row) for row in result],
                "count": total_count,
            }
        except Exception as e:
            log_error(f"Error fetching salary slips: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_by_id(id: int):
        try:
            query = select(
                salary_slips_table.c.id,
                salary_slips_table.c.userID,
                salary_slips_table.c.month,
                salary_slips_table.c.year,
                salary_slips_table.c.taxCategory,
                salary_slips_table.c.position,
                salary_slips_table.c.department,
                salary_slips_table.c.basicSalary,
                salary_slips_table.c.transportationAllowanceRate,
                salary_slips_table.c.transportationAllowanceQuantity,
                salary_slips_table.c.mealAllowanceRate,
                salary_slips_table.c.mealAllowanceQuantity,
                salary_slips_table.c.overtimeRate,
                salary_slips_table.c.overtimeQuantity,
                salary_slips_table.c.taxAmount,
                salary_slips_table.c.isDelete,
                salary_slips_table.c.bankName,
                salary_slips_table.c.bankAccountName,
                salary_slips_table.c.bankAccountNumber,
                salary_slips_table.c.paymentMethod,
                employees_table.c.name,
                employees_table.c.nik,
            ).join(
                employees_table, salary_slips_table.c.userID == employees_table.c.id
            ).where(
                salary_slips_table.c.id == id
            )
            result = await database.fetch_one(query)
            if not result:
                return {"error": "Salary slip not found", "status": 404}
            return dict(result)
        except Exception as e:
            log_error(f"Error fetching salary slip by ID: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def delete_by_id(id: int, userID: int):
        query = (
            update(salary_slips_table)
            .where(salary_slips_table.c.id == id)
            .values({
                "isDelete": True,
                "deletedBy": userID,
                'deletedAt': dt.now()
            })
        )

        result = await database.execute(query)
        if result == 0:
            return {"error": "Update failed or salary slip not found", "status": 404}
        
        from repository.audit_log_repository import AuditLogRepository

        await AuditLogRepository.record(
            entity="salary_slips",
            # entityID adalah id slip gaji. Kolom `userID` pada tabel ini
            # merujuk ke employees.id, sedangkan parameter userID di sini
            # adalah pelaku penghapusan — keduanya berbeda.
            entityID=id,
            action="delete",
            userID=userID,
        )

        return {"message": "Salary slip updated successfully"}

    @staticmethod
    async def update_payment_status(id: int, isPaid: bool, userID: int):
        # Keadaan sebelum & sesudah dibandingkan agar nilai lama ikut terekam.
        _sebelum = await database.fetch_one(
            select(salary_slips_table).where(salary_slips_table.c.id == id)
        )
        query = (
            update(salary_slips_table)
            .where(salary_slips_table.c.id == id)
            .values({
                "isPaid": isPaid,
                "updatedBy": userID,
                "updatedAt": dt.now()
            })
        )

        result = await database.execute(query)
        if result == 0:
            return {"error": "Update failed or salary slip not found", "status": 404}
        
        from repository.audit_log_repository import AuditLogRepository

        await AuditLogRepository.record(
            entity="salary_slips",
            # entityID adalah id slip gaji, bukan id pengguna yang mengubah.
            entityID=id,
            action="update_payment_status",
            userID=userID,
            changes=AuditLogRepository.diff(
                dict(_sebelum) if _sebelum else {},
                dict(
                    await database.fetch_one(
                        select(salary_slips_table).where(
                            salary_slips_table.c.id == id
                        )
                    )
                    or {}
                ),
            ),
        )

        return {"message": "Salary slip updated successfully"}

    @staticmethod
    async def get_allowances_by_salary_slip_id(salary_slip_id: int):
        query = select(salary_slips_allowance_table).where(
            salary_slips_allowance_table.c.salarySlipID == salary_slip_id
        )
        try:
            result = await database.fetch_all(query)
            return [dict(row) for row in result]
        except Exception as e:
            log_error(f"Error fetching allowances: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_deductions_by_salary_slip_id(salary_slip_id: int):
        query = select(salary_slips_deduction_table).where(
            salary_slips_deduction_table.c.salarySlipID == salary_slip_id
        )
        try:
            result = await database.fetch_all(query)
            return [dict(row) for row in result]
        except Exception as e:
            log_error(f"Error fetching deductions: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_pph_report(month: int, year: int):
        query = select(
            salary_slips_table.c.id,
            salary_slips_table.c.userID,
            salary_slips_table.c.month,
            salary_slips_table.c.year,
            salary_slips_table.c.taxCategory,
            salary_slips_table.c.position,
            salary_slips_table.c.department,
            salary_slips_table.c.basicSalary,
            salary_slips_table.c.transportationAllowanceRate, 
            salary_slips_table.c.transportationAllowanceQuantity,
            salary_slips_table.c.mealAllowanceRate, 
            salary_slips_table.c.mealAllowanceQuantity,
            salary_slips_table.c.overtimeRate, 
            salary_slips_table.c.overtimeQuantity,
            salary_slips_table.c.taxAmount,
            salary_slips_table.c.isDelete,
            salary_slips_table.c.isPaid,
            employees_table.c.name,
            employees_table.c.nik,
        ).join(
            employees_table, salary_slips_table.c.userID == employees_table.c.id
        ).where(
            salary_slips_table.c.month == month, 
            salary_slips_table.c.year == year, 
            salary_slips_table.c.isDelete == False 
        ).order_by(
           employees_table.c.name.asc()
        )
        
        allowance_query = (
            select(*salary_slips_allowance_table.c)
            .join(
                salary_slips_table, salary_slips_table.c.id == salary_slips_allowance_table.c.salarySlipID
            )
            .where(
                salary_slips_table.c.month == month, 
                salary_slips_table.c.year == year
            )
        )

        deduction_query = (
            select(*salary_slips_deduction_table.c)
            .join(
                salary_slips_table, salary_slips_table.c.id == salary_slips_deduction_table.c.salarySlipID
            )
            .where(
                salary_slips_table.c.month == month, 
                salary_slips_table.c.year == year
            )
        )
        
        try:
            result = await database.fetch_all(query)
            allowances = await database.fetch_all(allowance_query)
            deductions = await database.fetch_all(deduction_query)
            
            # Convert to list of dicts for easier manipulation
            result_data = [dict(row) for row in result]
            allowances_data = [dict(a) for a in allowances]
            deductions_data = [dict(d) for d in deductions]

            from collections import defaultdict
            
            allowance_map = defaultdict(list)
            for a in allowances_data:
                allowance_map[a['salarySlipID']].append(a)

            deduction_map = defaultdict(list)
            for d in deductions_data:
                deduction_map[d['salarySlipID']].append(d)

            # Attach to each row
            for row in result_data:
                row_id = row['id']
                row['allowances'] = allowance_map.get(row_id, [])
                row['deductions'] = deduction_map.get(row_id, [])

            return {
                "data": result_data,
            }

        except Exception as e:
            log_error(f"Error fetching PPH report: {str(e)}")
            return {"error": str(e), "status": 500}

class SalarySlipAllowanceRepository:
    @staticmethod
    async def create_allowances(salarySlipID: int, allowances: list):
        if not allowances:
            from repository.audit_log_repository import AuditLogRepository

            # Baris turunan dicatat pada dokumen induknya: riwayat dibaca
            # per dokumen, sehingga catatan terpisah tidak akan terlihat.
            await AuditLogRepository.record(
                entity="salary_slips",
                entityID=salarySlipID,
                action="create_allowances",
            )

            return {"message": "No allowances to create."}
        
        query = salary_slips_allowance_table.insert().values([
            {
                "salarySlipID": salarySlipID,
                "name": allowance['name'],
                "description": allowance['description'],
                "amount": allowance['amount'],
                "isIncluded": allowance['isIncluded']
            } for allowance in allowances
        ])

        try:
            await database.execute(query)
            return {"message": "Salary slip allowances created successfully."}
        except Exception as e:
            log_error(f"Error creating salary slip allowance: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_by_salary_slip_id(salarySlipID: int):
        query = salary_slips_allowance_table.select().where(salary_slips_allowance_table.c.salarySlipID == salarySlipID)
        try:
            result = await database.fetch_all(query)
            return [dict(row) for row in result]
        except Exception as e:
            log_error(f"Error fetching allowances: {str(e)}")
            return {"error": str(e), "status": 500}

class SalarySlipDeductionRepository:
    @staticmethod
    async def create_deductions(salarySlipID: int, deductions: list):
        if not deductions:
            from repository.audit_log_repository import AuditLogRepository

            # Baris turunan dicatat pada dokumen induknya: riwayat dibaca
            # per dokumen, sehingga catatan terpisah tidak akan terlihat.
            await AuditLogRepository.record(
                entity="salary_slips",
                entityID=salarySlipID,
                action="create_deductions",
            )

            return {"message": "No deductions to create."}
        
        query = salary_slips_deduction_table.insert().values([
            {
                "salarySlipID": salarySlipID,
                "name": deduction['name'],
                "description": deduction['description'],
                "amount": deduction['amount'],
                "isIncluded": deduction['isIncluded']
            } for deduction in deductions
        ])

        try:
            await database.execute(query)
            return {"message": "Salary slip deductions created successfully."}
        except Exception as e:
            log_error(f"Error creating salary slip deduction: {str(e)}")
            return {"error": str(e), "status": 500}
        
    @staticmethod
    async def get_by_salary_slip_id(salarySlipID: int):
        query = salary_slips_deduction_table.select().where(salary_slips_deduction_table.c.salarySlipID == salarySlipID)
        try:
            result = await database.fetch_all(query)
            return [dict(row) for row in result]
        except Exception as e:
            log_error(f"Error fetching deductions: {str(e)}")
            return {"error": str(e), "status": 500}