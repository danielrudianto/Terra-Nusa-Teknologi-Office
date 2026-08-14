from datetime import datetime as dt

from sqlalchemy import insert, select, update

from constants.employee_form_default import FORMULIR_BAWAAN, periksa_definisi
from models.employee_form_model import (
    employee_form_submissions_table,
    employee_form_versions_table,
)
from models.employee_model import employees_table
from utils.database import database
from utils.logger_utils import log_error


class EmployeeFormRepository:
    """
    Formulir keadaan karyawan yang ditanyakan berkala.

    Pertanyaannya disimpan bersama jawabannya lewat `versionID`: jawaban
    2026 selalu dibaca dengan pertanyaan 2026, walaupun formulir 2027 sudah
    berbeda.
    """

    # ---------------------------------------------------------------- versi

    @staticmethod
    async def list_versions():
        try:
            query = (
                select(employee_form_versions_table)
                .where(employee_form_versions_table.c.isDelete == False)
                .order_by(employee_form_versions_table.c.period.desc())
            )
            return [dict(r) for r in await database.fetch_all(query)]
        except Exception as e:
            log_error(f"Error listing form versions: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def active_version():
        """
        Versi yang sedang berlaku; None bila belum ada.

        None BUKAN galat: sebelum periode pertama dibuat, memang belum ada
        formulir yang dapat diisi — dan layarnya perlu menawarkan pembuatan
        periode, bukan menampilkan pesan gagal.
        """
        try:
            query = select(employee_form_versions_table).where(
                employee_form_versions_table.c.isActive == True,
                employee_form_versions_table.c.isDelete == False,
            )
            row = await database.fetch_one(query)
            return dict(row) if row else None
        except Exception as e:
            log_error(f"Error fetching active form version: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def create_version(data: dict, user_id: int):
        """
        Buat periode baru.

        Susunan pertanyaan DISALIN ke barisnya, bukan dirujuk dari kode.
        Bila dirujuk, mengubah berkas definisi akan diam-diam mengubah arti
        seluruh jawaban lama — dan tidak ada yang menyadarinya sampai ada
        yang membandingkan dua tahun.
        """
        try:
            periode = (data.get("period") or "").strip()
            if not periode:
                return {"error": "Period is required", "status": 400}

            ada = await database.fetch_one(
                select(employee_form_versions_table.c.id).where(
                    employee_form_versions_table.c.period == periode,
                    employee_form_versions_table.c.isDelete == False,
                )
            )
            if ada:
                return {
                    "error": f"Period {periode} already exists",
                    "status": 409,
                }

            definisi = data.get("fields") or FORMULIR_BAWAAN
            masalah = periksa_definisi(definisi)
            if masalah:
                # Ditolak SEKARANG, bukan saat karyawan membuka formulirnya
                # dan menemukan isian yang tidak muncul.
                return {
                    "error": "Form definition is invalid: " + "; ".join(masalah),
                    "status": 400,
                }

            import json

            nilai = {
                "period": periode,
                "title": (data.get("title") or f"Pembaruan data karyawan {periode}"),
                "description": data.get("description"),
                "fields": json.dumps(definisi),
                "isActive": bool(data.get("isActive", True)),
                "isDelete": False,
                # Default kolom sisi-Python tidak pernah berlaku pada
                # `databases`; diisi manual agar tidak sampai sebagai NULL.
                "createdAt": dt.now(),
                "createdBy": user_id,
            }

            if nilai["isActive"]:
                # Hanya satu versi aktif. Dua versi aktif membuat karyawan
                # yang berbeda mengisi formulir yang berbeda pada periode
                # yang sama, dan hasilnya tidak dapat dibandingkan.
                await database.execute(
                    update(employee_form_versions_table)
                    .where(employee_form_versions_table.c.isActive == True)
                    .values(isActive=False, updatedAt=dt.now(), updatedBy=user_id)
                )

            version_id = await database.execute(
                insert(employee_form_versions_table).values(**nilai)
            )

            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="employee_form_versions",
                entityID=version_id,
                action="create",
                userID=user_id,
                changes={"period": periode},
            )
            return {"id": version_id}
        except Exception as e:
            log_error(f"Error creating form version: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    # ----------------------------------------------------------- pengisian

    @staticmethod
    async def get_submission(employee_id: int, version_id: int):
        """Jawaban satu karyawan untuk satu periode; None bila belum mengisi."""
        try:
            query = select(employee_form_submissions_table).where(
                employee_form_submissions_table.c.employeeID == employee_id,
                employee_form_submissions_table.c.versionID == version_id,
                employee_form_submissions_table.c.isDelete == False,
            )
            row = await database.fetch_one(query)
            return dict(row) if row else None
        except Exception as e:
            log_error(f"Error fetching form submission: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def save_submission(
        employee_id: int, version_id: int, answers: dict, user_id: int
    ):
        """
        Simpan jawaban; dibuat bila belum ada, diperbarui bila sudah.

        Dapat diperbarui kapan saja dalam periodenya. Siklusnya memang
        setahun, tetapi kontak darurat yang berubah bulan Maret tidak boleh
        menunggu sampai pengisian tahun depan.
        """
        try:
            karyawan = await database.fetch_one(
                select(employees_table.c.id).where(
                    employees_table.c.id == employee_id,
                    employees_table.c.isDelete == False,
                )
            )
            if not karyawan:
                return {"error": "Employee not found", "status": 404}

            versi = await database.fetch_one(
                select(employee_form_versions_table.c.id).where(
                    employee_form_versions_table.c.id == version_id,
                    employee_form_versions_table.c.isDelete == False,
                )
            )
            if not versi:
                return {"error": "Form version not found", "status": 404}

            import json

            lama = await database.fetch_one(
                select(employee_form_submissions_table.c.id).where(
                    employee_form_submissions_table.c.employeeID == employee_id,
                    employee_form_submissions_table.c.versionID == version_id,
                )
            )

            if lama:
                await database.execute(
                    update(employee_form_submissions_table)
                    .where(employee_form_submissions_table.c.id == lama["id"])
                    .values(
                        answers=json.dumps(answers, default=str),
                        updatedAt=dt.now(),
                        updatedBy=user_id,
                        isDelete=False,
                    )
                )
                submission_id = lama["id"]
                aksi = "update"
            else:
                submission_id = await database.execute(
                    insert(employee_form_submissions_table).values(
                        employeeID=employee_id,
                        versionID=version_id,
                        answers=json.dumps(answers, default=str),
                        submittedAt=dt.now(),
                        submittedBy=user_id,
                        isDelete=False,
                    )
                )
                aksi = "create"

            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="employee_form_submissions",
                entityID=submission_id,
                action=aksi,
                userID=user_id,
                # Isinya data pribadi; yang dicatat hanya BAGIAN mana yang
                # tersentuh, bukan jawabannya. Jejak audit terbuka bagi level
                # 5 seluruhnya, dan menyalin jawaban ke sana membuat
                # pembatasan wilayah HRD tidak ada artinya.
                changes={"sections": sorted(answers.keys())},
            )
            return {"id": submission_id}
        except Exception as e:
            log_error(f"Error saving form submission: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def pending(version_id: int):
        """
        Karyawan aktif yang belum mengisi periode ini.

        Yang belum mengisi tidak punya baris, sehingga diambil dengan join
        kiri luar — bukan dengan penanda "belum mengisi" yang harus dijaga
        tetap benar.
        """
        try:
            sub = employee_form_submissions_table
            query = (
                select(
                    employees_table.c.id,
                    employees_table.c.name,
                    employees_table.c.position,
                    employees_table.c.department,
                )
                .select_from(
                    employees_table.outerjoin(
                        sub,
                        (employees_table.c.id == sub.c.employeeID)
                        & (sub.c.versionID == version_id)
                        & (sub.c.isDelete == False),
                    )
                )
                .where(
                    employees_table.c.isDelete == False,
                    employees_table.c.endDate.is_(None),
                    sub.c.id.is_(None),
                )
                .order_by(employees_table.c.name.asc())
            )
            return [dict(r) for r in await database.fetch_all(query)]
        except Exception as e:
            log_error(f"Error listing pending submissions: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
