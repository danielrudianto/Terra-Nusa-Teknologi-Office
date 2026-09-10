"""
Aturan pencatatan kemajuan proyek.

Yang dijaga di sini hanya tiga hal, dan ketiganya karena angka ini dibaca
sebagai kurva — bukan sebagai daftar:

  1. Persennya masuk akal (0-100).
  2. Satu tanggal hanya punya satu catatan hidup.
  3. Proyeknya benar-benar ada.

Selebihnya sengaja tidak dibatasi. Angkanya BOLEH turun: pekerjaan yang harus
diulang memang mengurangi kemajuan, dan memaksanya naik terus akan
menyembunyikan persoalan yang paling mahal.
"""

from datetime import date as d

from fastapi import HTTPException

from repository.project_progress_repository import ProjectProgressRepository
from repository.project_repository import ProjectRepository
from utils.errors import internal_error
from utils.logger_utils import log_error, log_info


def _persen_wajar(nilai) -> float | None:
    """Kembalikan persennya bila sah, atau None."""
    try:
        angka = float(nilai)
    except (TypeError, ValueError):
        return None
    if angka < 0 or angka > 100:
        return None
    return angka


class ProjectProgressController:
    @staticmethod
    async def list_progress(project_id: int):
        log_info(f"Listing progress for project {project_id}")
        try:
            return await ProjectProgressRepository.list_by_project(project_id)
        except Exception as e:
            log_error(f"Error listing progress: {str(e)}")
            return internal_error()

    @staticmethod
    async def create_progress(project_id: int, data: dict, userID: int):
        log_info(f"Recording progress for project {project_id}: {data}")
        try:
            proyek = await ProjectRepository.get_by_id(project_id)
            if not proyek or (isinstance(proyek, dict) and "error" in proyek):
                return {"error": "Project not found", "status": 404}

            persen = _persen_wajar(data.get("percentage"))
            if persen is None:
                return {"error": "PROGRESS_PERCENTAGE_INVALID", "status": 400}

            tanggal = data.get("date")
            if not tanggal:
                return {"error": "PROGRESS_DATE_REQUIRED", "status": 400}

            if await ProjectProgressRepository.ada_pada_tanggal(project_id, tanggal):
                # Dua baris pada satu tanggal membuat kurvanya bercabang, dan
                # tidak ada cara membaca mana yang benar. Yang ingin
                # membetulkan angkanya menyunting baris yang sudah ada.
                return {"error": "PROGRESS_DATE_EXISTS", "status": 409}

            return await ProjectProgressRepository.create(
                project_id,
                tanggal,
                persen,
                (data.get("description") or None),
                userID,
            )
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error creating progress: {str(e)}")
            return internal_error()

    @staticmethod
    async def update_progress(progress_id: int, data: dict, userID: int):
        log_info(f"Updating progress {progress_id}: {data}")
        try:
            baris = await ProjectProgressRepository.get_by_id(progress_id)
            if baris is None:
                return {"error": "Progress not found", "status": 404}
            if baris["isDelete"]:
                return {"error": "Progress is already deleted", "status": 400}

            perubahan: dict = {}

            if "percentage" in data and data["percentage"] is not None:
                persen = _persen_wajar(data["percentage"])
                if persen is None:
                    return {"error": "PROGRESS_PERCENTAGE_INVALID", "status": 400}
                perubahan["percentage"] = persen

            if "date" in data and data["date"]:
                tanggal: d = data["date"]
                if await ProjectProgressRepository.ada_pada_tanggal(
                    baris["projectID"], tanggal, kecuali_id=progress_id
                ):
                    return {"error": "PROGRESS_DATE_EXISTS", "status": 409}
                perubahan["date"] = tanggal

            if "description" in data:
                perubahan["description"] = data["description"] or None

            if not perubahan:
                return {"error": "PROGRESS_NOTHING_TO_UPDATE", "status": 400}

            return await ProjectProgressRepository.update(
                progress_id, perubahan, userID
            )
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error updating progress: {str(e)}")
            return internal_error()

    @staticmethod
    async def delete_progress(progress_id: int, userID: int):
        log_info(f"Deleting progress {progress_id}")
        try:
            baris = await ProjectProgressRepository.get_by_id(progress_id)
            if baris is None:
                return {"error": "Progress not found", "status": 404}
            if baris["isDelete"]:
                return {"error": "Progress is already deleted", "status": 400}

            return await ProjectProgressRepository.delete(progress_id, userID)
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error deleting progress: {str(e)}")
            return internal_error()
