"""
Baca-tulis kemajuan proyek.

Seluruh kueri tabel `project_progress` ada di sini; controller tidak menyentuh
basis data sendiri.
"""

from datetime import date as d, datetime as dt

from sqlalchemy import select, func

from models.project_progress_model import project_progress_table
from utils.database import database
from utils.errors import internal_error
from utils.logger_utils import log_error


class ProjectProgressRepository:
    @staticmethod
    async def list_by_project(project_id: int):
        """
        Riwayat kemajuan satu proyek, terurut menurut tanggal keadaannya.

        Naik, bukan turun — berbeda dari daftar dokumen. Yang membacanya
        bukan mencari baris terbaru melainkan membaca sebuah kurva, dan kurva
        yang dibaca dari kanan ke kiri harus dibalik sendiri di layar.
        """
        query = (
            select(project_progress_table)
            .where(
                project_progress_table.c.projectID == project_id,
                project_progress_table.c.isDelete == False,  # noqa: E712
            )
            .order_by(project_progress_table.c.date.asc())
        )
        try:
            return await database.fetch_all(query)
        except Exception as e:
            log_error(f"Error fetching progress for project {project_id}: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_by_id(progress_id: int):
        query = select(project_progress_table).where(
            project_progress_table.c.id == progress_id
        )
        try:
            return await database.fetch_one(query)
        except Exception as e:
            log_error(f"Error fetching progress {progress_id}: {str(e)}")
            return None

    @staticmethod
    async def ada_pada_tanggal(
        project_id: int, tanggal: d, kecuali_id: int | None = None
    ) -> bool:
        """
        Apakah proyek ini sudah punya catatan HIDUP pada tanggal tersebut.

        Baris terhapus sengaja tidak dihitung: proyek yang catatannya keliru
        lalu dihapus harus dapat dicatat ulang pada tanggal yang sama. Itu
        pula sebabnya penjagaan ini ada di sini dan bukan berupa indeks unik
        di basis data — indeks tidak dapat membedakan keduanya.
        """
        syarat = [
            project_progress_table.c.projectID == project_id,
            project_progress_table.c.date == tanggal,
            project_progress_table.c.isDelete == False,  # noqa: E712
        ]
        if kecuali_id is not None:
            syarat.append(project_progress_table.c.id != kecuali_id)

        try:
            jumlah = await database.fetch_val(
                select(func.count()).select_from(project_progress_table).where(*syarat)
            )
            return bool(jumlah)
        except Exception as e:
            log_error(f"Error checking progress date for project {project_id}: {str(e)}")
            # Gagal memeriksa diperlakukan seolah tanggalnya SUDAH terisi:
            # menolak pencatatan yang mungkin sah lebih ringan akibatnya
            # daripada meloloskan dua baris pada satu tanggal, yang membuat
            # kurvanya bercabang tanpa ada yang tahu mana yang benar.
            return True

    @staticmethod
    async def create(
        project_id: int,
        tanggal: d,
        persen,
        keterangan: str | None,
        userID: int,
    ) -> dict:
        query = project_progress_table.insert().values(
            projectID=project_id,
            date=tanggal,
            percentage=persen,
            description=keterangan,
            createdAt=dt.now(),
            createdBy=userID,
            isDelete=False,
        )
        try:
            baru = await database.execute(query)

            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="project_progress",
                entityID=int(baru),
                action="create",
                userID=userID,
            )
            return {"message": "Progress recorded", "id": baru}
        except Exception as e:
            log_error(f"Error creating progress for project {project_id}: {str(e)}")
            return internal_error()

    @staticmethod
    async def update(progress_id: int, perubahan: dict, userID: int) -> dict:
        # Keadaan SEBELUM diubah diambil lebih dulu; sesudah `execute` nilai
        # lamanya sudah tertimpa dan tidak dapat direkam lagi.
        sebelum = await ProjectProgressRepository.get_by_id(progress_id)
        if sebelum is None:
            return {"error": "Progress not found", "status": 404}

        nilai = dict(perubahan)
        nilai["updatedAt"] = dt.now()
        nilai["updatedBy"] = userID

        try:
            await database.execute(
                project_progress_table.update()
                .where(project_progress_table.c.id == progress_id)
                .values(**nilai)
            )

            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="project_progress",
                entityID=int(progress_id),
                action="update",
                userID=userID,
                changes=AuditLogRepository.diff(dict(sebelum), perubahan),
            )
            return {"message": "Progress updated"}
        except Exception as e:
            log_error(f"Error updating progress {progress_id}: {str(e)}")
            return internal_error()

    @staticmethod
    async def delete(progress_id: int, userID: int) -> dict:
        try:
            hasil = await database.execute(
                project_progress_table.update()
                .where(
                    project_progress_table.c.id == progress_id,
                    project_progress_table.c.isDelete == False,  # noqa: E712
                )
                .values(isDelete=True, deletedAt=dt.now(), deletedBy=userID)
            )
            if not hasil:
                return {"error": "Progress not found", "status": 404}

            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="project_progress",
                entityID=int(progress_id),
                action="delete",
                userID=userID,
            )
            return {"message": "Progress deleted"}
        except Exception as e:
            log_error(f"Error deleting progress {progress_id}: {str(e)}")
            return internal_error()
