from typing import Any, Dict, Optional
from sqlalchemy import select, insert, update, func, or_, and_
from sqlalchemy.exc import IntegrityError
from datetime import datetime as dt
from decimal import Decimal

from utils.database import database
from utils.logger_utils import log_error
from models.project_model import projects_table, project_contracts_table


def _nilai_kontrak_subquery():
    """
    Jumlah nilai kontrak per proyek, hanya baris yang belum dihapus.

    Dipakai sebagai subquery, bukan dihitung di Python setelah data diambil:
    daftar proyek memakai paginasi, sehingga menghitung di Python berarti
    mengambil seluruh baris kontrak setiap kali halaman dibuka.
    """
    return (
        select(
            project_contracts_table.c.projectID.label("pid"),
            func.coalesce(func.sum(project_contracts_table.c.value), 0).label("total"),
            func.coalesce(func.sum(project_contracts_table.c.dpp), 0).label("dpp"),
            func.count(project_contracts_table.c.id).label("jumlah"),
        )
        .where(project_contracts_table.c.isDelete == False)  # noqa: E712
        .group_by(project_contracts_table.c.projectID)
        .subquery()
    )


class ProjectRepository:
    # ---- Proyek -----------------------------------------------------------

    @staticmethod
    async def create(data: dict, user_id: int) -> Dict[str, Any]:
        try:
            query = insert(projects_table).values(
                **data,
                createdAt=dt.now(),
                createdBy=user_id,
                isDelete=False,
            )
            project_id = await database.execute(query)

            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="projects", entityID=project_id, action="create"
            )
            return {"message": "Project created successfully", "project_id": project_id}
        except IntegrityError:
            # Satu-satunya batasan unik di tabel ini adalah `code`.
            return {"error": "PROJECT_CODE_EXISTS", "status": 409}
        except Exception as e:
            log_error(f"Error creating project: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_by_id(project_id: int):
        agg = _nilai_kontrak_subquery()
        query = (
            select(
                projects_table,
                func.coalesce(agg.c.total, 0).label("contractValue"),
                func.coalesce(agg.c.dpp, 0).label("contractDpp"),
                func.coalesce(agg.c.jumlah, 0).label("contractCount"),
            )
            .select_from(
                projects_table.outerjoin(agg, agg.c.pid == projects_table.c.id)
            )
            .where(
                projects_table.c.id == project_id,
                projects_table.c.isDelete == False,  # noqa: E712
            )
        )
        return await database.fetch_one(query)

    @staticmethod
    async def get_by_code(code: str):
        query = select(projects_table).where(
            func.upper(projects_table.c.code) == (code or "").strip().upper(),
            projects_table.c.isDelete == False,  # noqa: E712
        )
        return await database.fetch_one(query)

    @staticmethod
    async def get_all(
        keyword: Optional[str] = None,
        isActive: Optional[bool] = None,
        isCancelled: Optional[bool] = None,
        page: int = 1,
        pageSize: int = 10,
        sortBy: Optional[str] = None,
        sortByDirection: str = "asc",
    ) -> Dict[str, Any]:
        try:
            agg = _nilai_kontrak_subquery()
            syarat = [projects_table.c.isDelete == False]  # noqa: E712
            if keyword:
                pola = f"%{keyword}%"
                syarat.append(
                    or_(
                        projects_table.c.code.like(pola),
                        projects_table.c.name.like(pola),
                    )
                )
            # Dibandingkan dengan `is not None`, bukan kebenaran nilainya:
            # `isActive=False` adalah penyaringan yang sah dan tidak boleh
            # terbaca sebagai "tidak menyaring".
            if isActive is not None:
                syarat.append(projects_table.c.isActive == isActive)
            if isCancelled is not None:
                syarat.append(projects_table.c.isCancelled == isCancelled)

            kolom = {
                "code": projects_table.c.code,
                "name": projects_table.c.name,
                "isActive": projects_table.c.isActive,
                "isCancelled": projects_table.c.isCancelled,
                "startDate": projects_table.c.startDate,
                "contractValue": func.coalesce(agg.c.total, 0),
            }
            urut = kolom.get(sortBy or "code", projects_table.c.code)
            urut = urut.desc() if sortByDirection == "desc" else urut.asc()

            dasar = projects_table.outerjoin(agg, agg.c.pid == projects_table.c.id)

            total = await database.fetch_val(
                select(func.count()).select_from(projects_table).where(and_(*syarat))
            )

            rows = await database.fetch_all(
                select(
                    projects_table,
                    func.coalesce(agg.c.total, 0).label("contractValue"),
                func.coalesce(agg.c.dpp, 0).label("contractDpp"),
                    func.coalesce(agg.c.jumlah, 0).label("contractCount"),
                )
                .select_from(dasar)
                .where(and_(*syarat))
                .order_by(urut)
                .limit(pageSize)
                .offset((max(page, 1) - 1) * pageSize)
            )
            return {"data": [dict(r) for r in rows], "count": total or 0}
        except Exception as e:
            log_error(f"Error listing projects: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def count_documents(code: str) -> int:
        """
        Berapa dokumen yang sudah memakai kode proyek ini.

        Kode disimpan sebagai TEKS pada dokumen, bukan tautan ke baris ini —
        `purchases.projectName`, `purchase_orders.projectName`, dan
        seterusnya. Mengubah kodenya tidak ikut memperbarui dokumen lama:
        yang lama tetap menyebut kode lama, sehingga laporan per proyek
        terpecah menjadi dua tanpa ada yang menyadarinya.

        Karena itu penggantian hanya diizinkan selama belum ada dokumen yang
        memakainya — cukup untuk membetulkan salah ketik, tanpa memutus
        jejak yang sudah terbit.
        """
        from models.purchase_draft_model import purchase_draft_table
        from models.purchase_model import purchases_table
        from models.purchase_order_model import purchase_orders_table
        from models.reimbursement_model import reimbursements_table
        from models.sales_invoice_model import sales_invoice_tables

        total = 0
        for tabel in (
            purchases_table,
            purchase_orders_table,
            purchase_draft_table,
            reimbursements_table,
            sales_invoice_tables,
        ):
            n = await database.fetch_val(
                select(func.count()).select_from(tabel).where(
                    tabel.c.projectName == code
                )
            )
            total += int(n or 0)
        return total

    @staticmethod
    async def update(project_id: int, values: dict, user_id: int) -> Dict[str, Any]:
        try:
            _sebelum = await database.fetch_one(
                select(projects_table).where(projects_table.c.id == project_id)
            )
            if _sebelum is None:
                return {"error": "Project not found", "status": 404}

            values = {**values, "updatedAt": dt.now(), "updatedBy": user_id}
            await database.execute(
                update(projects_table)
                .where(projects_table.c.id == project_id)
                .where(projects_table.c.isDelete == False)  # noqa: E712
                .values(**values)
            )

            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="projects",
                entityID=project_id,
                action="update",
                changes=AuditLogRepository.diff(dict(_sebelum), values),
            )
            return {"message": "Project updated successfully", "project_id": project_id}
        except Exception as e:
            log_error(f"Error updating project: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def soft_delete(project_id: int, user_id: int) -> Dict[str, Any]:
        try:
            await database.execute(
                update(projects_table)
                .where(projects_table.c.id == project_id)
                .values(isDelete=True, deletedAt=dt.now(), deletedBy=user_id)
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="projects", entityID=project_id, action="delete"
            )
            return {"message": "Project deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting project: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    # ---- Kontrak ----------------------------------------------------------

    @staticmethod
    async def list_contracts(project_id: int):
        query = (
            select(project_contracts_table)
            .where(
                project_contracts_table.c.projectID == project_id,
                project_contracts_table.c.isDelete == False,  # noqa: E712
            )
            .order_by(project_contracts_table.c.date.asc())
        )
        return await database.fetch_all(query)

    @staticmethod
    def _nilai_dokumen(data: dict) -> dict:
        """
        Isi `value` dari DPP dan PPN.

        Dihitung di server, bukan diterima dari klien: kalau angkanya boleh
        dikirim, nominal dokumen bisa tidak cocok dengan komponennya dan
        tidak ada yang tahu mana yang benar.
        """
        if "dpp" in data:
            dpp = Decimal(str(data.get("dpp") or 0))
            ppn = Decimal(str(data.get("ppn") or 0))
            data["value"] = dpp + (dpp * ppn / Decimal(100))
        return data

    @staticmethod
    async def add_contract(project_id: int, data: dict, user_id: int) -> Dict[str, Any]:
        try:
            data = ProjectRepository._nilai_dokumen(data)
            contract_id = await database.execute(
                insert(project_contracts_table).values(
                    **data,
                    projectID=project_id,
                    createdAt=dt.now(),
                    createdBy=user_id,
                    isDelete=False,
                )
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="project_contracts", entityID=contract_id, action="create"
            )
            return {"message": "Contract added successfully", "contract_id": contract_id}
        except Exception as e:
            log_error(f"Error adding contract: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_contract(contract_id: int):
        return await database.fetch_one(
            select(project_contracts_table).where(
                project_contracts_table.c.id == contract_id,
                project_contracts_table.c.isDelete == False,  # noqa: E712
            )
        )

    @staticmethod
    async def update_contract(
        contract_id: int, values: dict, user_id: int
    ) -> Dict[str, Any]:
        try:
            _sebelum = await database.fetch_one(
                select(project_contracts_table).where(
                    project_contracts_table.c.id == contract_id
                )
            )
            if _sebelum is None:
                return {"error": "Contract not found", "status": 404}

            values = ProjectRepository._nilai_dokumen(
                {**values, "updatedAt": dt.now(), "updatedBy": user_id}
            )
            await database.execute(
                update(project_contracts_table)
                .where(project_contracts_table.c.id == contract_id)
                .where(project_contracts_table.c.isDelete == False)  # noqa: E712
                .values(**values)
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="project_contracts",
                entityID=contract_id,
                action="update",
                changes=AuditLogRepository.diff(dict(_sebelum), values),
            )
            return {"message": "Contract updated successfully"}
        except Exception as e:
            log_error(f"Error updating contract: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def delete_contract(contract_id: int, user_id: int) -> Dict[str, Any]:
        try:
            await database.execute(
                update(project_contracts_table)
                .where(project_contracts_table.c.id == contract_id)
                .values(isDelete=True, deletedAt=dt.now(), deletedBy=user_id)
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="project_contracts", entityID=contract_id, action="delete"
            )
            return {"message": "Contract deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting contract: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
