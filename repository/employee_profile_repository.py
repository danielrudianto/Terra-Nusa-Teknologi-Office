from datetime import datetime as dt

from sqlalchemy import insert, select, update

from models.employee_model import employees_table
from models.employee_profile_model import employee_profiles_table
from utils.database import database
from utils.logger_utils import log_error


class EmployeeProfileRepository:
    """
    Profil pribadi karyawan — satu baris per orang.

    Diisi sekali saat karyawan masuk, disunting bila ada koreksi. Yang
    berubah tiap tahun tidak di sini melainkan di formulir berkala.
    """

    @staticmethod
    async def get_by_employee(employee_id: int):
        """
        Profil satu karyawan; None bila belum pernah diisi.

        Belum diisi BUKAN galat: karyawan lama sudah ada sebelum tabel ini
        dibuat, dan layarnya perlu membedakan "belum diisi" dari "gagal
        dibaca" agar dapat menampilkan formulir kosong, bukan pesan galat.
        """
        try:
            query = select(employee_profiles_table).where(
                employee_profiles_table.c.employeeID == employee_id
            )
            row = await database.fetch_one(query)
            return dict(row) if row else None
        except Exception as e:
            log_error(f"Error fetching employee profile: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def upsert(employee_id: int, data: dict, user_id: int):
        """
        Simpan profil: buat bila belum ada, perbarui bila sudah.

        Satu jalur, bukan create dan update terpisah. Dari sisi pemakainya
        ini satu formulir yang disimpan; memisahkannya memaksa layar
        mengetahui lebih dulu apakah profilnya sudah ada, dan menebak salah
        berarti galat kunci ganda yang tidak dapat dijelaskan penggunanya.
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

            bersih = {k: v for k, v in data.items() if v is not None}
            lama = await database.fetch_one(
                select(employee_profiles_table.c.id).where(
                    employee_profiles_table.c.employeeID == employee_id
                )
            )

            if lama:
                bersih["updatedAt"] = dt.now()
                bersih["updatedBy"] = user_id
                await database.execute(
                    update(employee_profiles_table)
                    .where(employee_profiles_table.c.id == lama["id"])
                    .values(**bersih)
                )
                profile_id = lama["id"]
                aksi = "update"
            else:
                bersih["employeeID"] = employee_id
                # Diisi manual: default kolom sisi-Python tidak pernah
                # berlaku pada `databases`, dan nilainya sampai ke MySQL
                # sebagai NULL pada kolom NOT NULL.
                bersih["createdAt"] = dt.now()
                bersih["createdBy"] = user_id
                profile_id = await database.execute(
                    insert(employee_profiles_table).values(**bersih)
                )
                aksi = "create"

            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="employee_profiles",
                entityID=profile_id,
                action=aksi,
                userID=user_id,
                # Isinya data pribadi; yang dicatat hanya NAMA kolom yang
                # tersentuh, bukan nilainya. Jejak audit dapat dibaca level
                # 5 seluruhnya, dan menyalin isi profil ke sana membuat
                # pembatasan wilayahnya tidak ada artinya.
                changes={"fields": sorted(k for k in bersih if k not in
                                          ("createdAt", "createdBy",
                                           "updatedAt", "updatedBy"))},
            )
            return {"id": profile_id}
        except Exception as e:
            log_error(f"Error saving employee profile: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def missing_profiles():
        """
        Karyawan aktif yang belum punya profil.

        Dipakai HRD untuk menagih. Yang belum mengisi tidak punya baris di
        tabel profil, sehingga daftarnya diambil dengan join kiri luar —
        bukan dengan menyimpan penanda "belum diisi" yang harus dijaga
        tetap benar.
        """
        try:
            query = (
                select(
                    employees_table.c.id,
                    employees_table.c.name,
                    employees_table.c.position,
                    employees_table.c.department,
                )
                .select_from(
                    employees_table.outerjoin(
                        employee_profiles_table,
                        employees_table.c.id
                        == employee_profiles_table.c.employeeID,
                    )
                )
                .where(
                    employees_table.c.isDelete == False,
                    employees_table.c.endDate.is_(None),
                    employee_profiles_table.c.id.is_(None),
                )
                .order_by(employees_table.c.name.asc())
            )
            rows = await database.fetch_all(query)
            return [dict(r) for r in rows]
        except Exception as e:
            log_error(f"Error fetching employees without profile: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
