import json
from datetime import datetime as dt

from sqlalchemy import insert, select, update

from models.employee_model import employees_table
from models.employee_profile_model import (
    employee_profile_history_table,
    employee_profiles_table,
)
from models.user_model import users_table
from utils.database import database
from utils.logger_utils import log_error



#: Kolom JSON yang dapat kembali sebagai TEKS dari driver.
#:
#: `databases` mengembalikan kolom JSON MySQL apa adanya — sebagai string,
#: bukan objek Python. Layar memeriksanya dengan `Array.isArray()`, yang
#: menolak string, sehingga seluruh bagian itu tidak pernah ditampilkan.
#:
#: Tidak ada galat di mana pun: datanya tersimpan benar, jawabannya berisi,
#: dan layarnya menyimpulkan bagian itu memang kosong. Yang membukanya
#: menanyakan ulang pendidikan dan susunan keluarga kepada orangnya.
#:
#: Pola yang sama sudah dipakai `purchase_order_repository`.
_KOLOM_JSON = (
    "drivingLicenses",
    "formalEducation",
    "workExperience",
    "languages",
    "familyMembers",
)


def _rapikan(row):
    """Baris database menjadi dict biasa, dengan kolom JSON sudah diurai."""
    if row is None:
        return None
    data = dict(row)
    for kolom in _KOLOM_JSON:
        nilai = data.get(kolom)
        if isinstance(nilai, str):
            try:
                data[kolom] = json.loads(nilai)
            except (ValueError, TypeError):
                # Isi yang tidak dapat diurai DIBIARKAN apa adanya.
                #
                # Mengosongkannya menghapus data yang mungkin masih dapat
                # diselamatkan tangan; membiarkannya membuat masalahnya
                # terlihat, bukan hilang diam-diam.
                pass
    return data


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
            return _rapikan(row)
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

                # Keadaan SEBELUM ditimpa disalin lebih dulu.
                #
                # Profil hanya punya satu baris per karyawan; tanpa salinan
                # ini, satu koreksi yang keliru menghapus nilai sebelumnya
                # untuk selamanya. Jejak audit umum tidak menggantikannya —
                # ia sengaja hanya mencatat NAMA kolom, bukan isinya.
                #
                # Disalin SEBELUM `update` dijalankan, bukan sesudah: sesudah
                # itu yang terbaca sudah nilai barunya.
                sebelum = await database.fetch_one(
                    select(employee_profiles_table).where(
                        employee_profiles_table.c.id == lama["id"]
                    )
                )
                if sebelum is not None:
                    await database.execute(
                        insert(employee_profile_history_table).values(
                            profileID=lama["id"],
                            employeeID=employee_id,
                            # `default=str` diperlukan: profil memuat tanggal,
                            # dan tanggal tidak dapat diserialkan JSON sendiri.
                            snapshot=json.dumps(dict(sebelum), default=str),
                            changedFields=json.dumps(
                                sorted(
                                    k
                                    for k in bersih
                                    if k not in ("updatedAt", "updatedBy")
                                )
                            ),
                            changedAt=dt.now(),
                            changedBy=user_id,
                        )
                    )

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
            return [_rapikan(r) for r in rows]
        except Exception as e:
            log_error(f"Error fetching employees without profile: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def history(employee_id: int):
        """
        Riwayat perubahan profil seorang karyawan, terbaru lebih dulu.

        Yang dikembalikan adalah keadaan SEBELUM tiap perubahan, beserta siapa
        yang mengubah dan kapan. Dengan itu koreksi yang keliru dapat
        dikembalikan — dan yang lebih sering diperlukan: dapat dibuktikan
        bahwa nilainya memang pernah begitu.

        Dibaca dengan izin yang sama dengan profilnya sendiri; isinya data
        yang sama.
        """
        try:
            pengubah = users_table.alias("pengubah")
            query = (
                select(
                    employee_profile_history_table.c.id,
                    employee_profile_history_table.c.employeeID,
                    employee_profile_history_table.c.snapshot,
                    employee_profile_history_table.c.changedFields,
                    employee_profile_history_table.c.changedAt,
                    employee_profile_history_table.c.changedBy,
                    pengubah.c.name.label("changedByName"),
                )
                .select_from(
                    employee_profile_history_table.outerjoin(
                        pengubah,
                        employee_profile_history_table.c.changedBy
                        == pengubah.c.id,
                    )
                )
                .where(
                    employee_profile_history_table.c.employeeID == employee_id
                )
                .order_by(employee_profile_history_table.c.changedAt.desc())
            )
            rows = await database.fetch_all(query)

            hasil = []
            for r in rows:
                data = dict(r)
                # Sama seperti kolom JSON lain: `databases` mengembalikannya
                # sebagai teks, dan layar yang memeriksanya dengan
                # `Array.isArray()` akan menyimpulkan riwayatnya kosong.
                for kunci in ("snapshot", "changedFields"):
                    nilai = data.get(kunci)
                    if isinstance(nilai, str):
                        try:
                            data[kunci] = json.loads(nilai)
                        except (ValueError, TypeError):
                            pass
                hasil.append(data)
            return hasil
        except Exception as e:
            log_error(f"Error fetching employee profile history: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
