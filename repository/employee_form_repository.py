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



def kategori_pajak(status_nikah, tanggungan) -> str:
    """
    Kategori PTKP dari status pernikahan dan jumlah tanggungan.

    Hanya "Kawin" menghasilkan awalan `K`. Cerai dan duda/janda kembali ke
    `TK`: PTKP mengikuti keadaan pada awal tahun pajak, dan yang menentukan
    adalah ada tidaknya pasangan — bukan pernah tidaknya menikah.

    Tanggungan dibatasi TIGA. Batas itu bukan pilihan kami; PTKP memang tidak
    mengakui lebih dari tiga, dan membiarkan angka keempat masuk membuat
    kategori yang tidak ada seperti `K/4`.
    """
    kawin = str(status_nikah or "").strip().lower() == "kawin"
    try:
        n = int(tanggungan or 0)
    except (TypeError, ValueError):
        n = 0
    n = max(0, min(3, n))
    return f"{'K' if kawin else 'TK'}/{n}"


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
        Definisi pertanyaan yang sedang berlaku.

        BUKAN periode. Sejak pembaruan data dapat dilakukan kapan saja, versi
        di sini hanya menandai BENTUK PERTANYAANNYA — ia bertambah ketika
        daftar pertanyaannya diubah, bukan tiap tahun.

        Dibuat OTOMATIS bila belum ada. Tanpa itu layar formulir buntu:
        tidak ada pertanyaan untuk ditampilkan, dan tidak ada tempat bagi
        pengguna untuk membuatnya karena pembuatan periode sudah dibuang.
        """
        try:
            query = select(employee_form_versions_table).where(
                employee_form_versions_table.c.isActive == True,  # noqa: E712
                employee_form_versions_table.c.isDelete == False,  # noqa: E712
            )
            row = await database.fetch_one(query)
            if row:
                return dict(row)

            return await EmployeeFormRepository._buat_versi_bawaan()
        except Exception as e:
            log_error(f"Error fetching active form version: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def _buat_versi_bawaan():
        """
        Terbitkan definisi pertanyaan bawaan.

        Dipanggil sekali saja seumur basis data — pemanggilan berikutnya
        menemukan versi yang sudah aktif dan tidak sampai ke sini.

        Bila dua permintaan tiba bersamaan dan keduanya membuat versi, yang
        kedua ditemukan lebih dulu pada pembacaan ulang di bawah; barisnya
        boleh kembar sesaat, dan yang dipakai tetap satu.
        """
        import json

        from constants.employee_form_default import FORMULIR_BAWAAN

        try:
            await database.execute(
                insert(employee_form_versions_table).values(
                    period="-",
                    title="Pembaruan data karyawan",
                    description=None,
                    fields=json.dumps(FORMULIR_BAWAAN),
                    isActive=True,
                    isDelete=False,
                    createdAt=dt.now(),
                    createdBy=1,
                )
            )
            row = await database.fetch_one(
                select(employee_form_versions_table)
                .where(
                    employee_form_versions_table.c.isActive == True,  # noqa: E712
                    employee_form_versions_table.c.isDelete == False,  # noqa: E712
                )
                .order_by(employee_form_versions_table.c.id.desc())
                .limit(1)
            )
            return dict(row) if row else None
        except Exception as e:
            log_error(f"Error creating default form version: {str(e)}")
            return None

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
    async def kedaluwarsa(batas_bulan: int = 12, jangkauan_hari: int = 30):
        """
        Karyawan yang datanya perlu dikonfirmasi ulang.

        Yang dihitung adalah pembaruan data karyawan APA PUN — mengisi profil
        pribadi maupun menyimpan formulir keadaan. Keduanya sama-sama berarti
        datanya baru saja ditinjau, dan memisahkannya membuat orang yang
        profilnya baru diisi tetap tertagih seolah belum pernah menyentuh
        datanya.

        Tiga kelompok masuk ke sini:
          - yang pembaruan terakhirnya lebih dari `batas_bulan`;
          - yang baru mengisi salah satunya lebih dari `batas_bulan` lalu;
          - yang belum pernah mengisi apa pun.

        Ketiganya memerlukan tindakan yang sama dari HRD, jadi tidak dibedakan
        pada daftarnya — yang membedakan hanya kolom `terakhir`, yang kosong
        bagi yang belum pernah.

        `jangkauan_hari` memunculkannya SEBELUM jatuh tempo. Tiga puluh hari,
        bukan tujuh seperti ulang tahun: mengumpulkan data karyawan perlu
        menghubungi orangnya, menunggu jawabannya, dan kerap menunggu ia
        pulang dari lapangan.

        Karyawan yang sudah keluar tidak ikut: menanyakan data orang yang
        tidak lagi bekerja tidak ada gunanya.
        """
        try:
            rows = await database.fetch_all(
                """
                SELECT
                    e.id,
                    e.name,
                    e.position,
                    -- Yang paling akhir di antara KEDUA sumber.
                    --
                    -- `updatedAt` profil bernilai NULL sampai ada penyuntingan
                    -- pertama, sehingga `createdAt` dipakai sebagai
                    -- cadangannya — mengisi profil pertama kali juga sebuah
                    -- peninjauan data.
                    GREATEST(
                        COALESCE(p.updatedAt, p.createdAt, '1000-01-01'),
                        COALESCE(MAX(s.submittedAt), '1000-01-01')
                    ) AS terakhir_mentah,
                    NULLIF(
                        GREATEST(
                            COALESCE(p.updatedAt, p.createdAt, '1000-01-01'),
                            COALESCE(MAX(s.submittedAt), '1000-01-01')
                        ),
                        '1000-01-01'
                    ) AS terakhir
                FROM employees e
                LEFT JOIN employee_profiles p
                       ON p.employeeID = e.id
                LEFT JOIN employee_form_submissions s
                       ON s.employeeID = e.id AND s.isDelete = 0
                WHERE e.isDelete = 0
                  AND e.endDate IS NULL
                GROUP BY e.id, e.name, e.position, p.updatedAt, p.createdAt
                HAVING terakhir IS NULL
                    OR terakhir <= DATE_SUB(
                           DATE_ADD(NOW(), INTERVAL :jangkauan DAY),
                           INTERVAL :bulan MONTH
                       )
                ORDER BY terakhir IS NOT NULL, terakhir ASC
                """,
                {"bulan": batas_bulan, "jangkauan": jangkauan_hari},
            )
            hasil = []
            for r in rows:
                d = dict(r)
                d.pop("terakhir_mentah", None)
                hasil.append(d)
            return hasil
        except Exception as e:
            log_error(f"Error listing stale employee forms: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def riwayat(employee_id: int):
        """
        Seluruh pembaruan seorang karyawan, terbaru lebih dulu.

        Dipakai melihat apa yang berubah dan kapan — alamat lama, jumlah
        tanggungan sebelumnya. Yang berlaku selalu baris pertama.
        """
        try:
            rows = await database.fetch_all(
                """
                SELECT s.id, s.answers, s.submittedAt, s.submittedBy,
                       u.name AS submittedByName, s.versionID
                FROM employee_form_submissions s
                LEFT JOIN users u ON u.id = s.submittedBy
                WHERE s.employeeID = :id AND s.isDelete = 0
                ORDER BY s.submittedAt DESC
                """,
                {"id": employee_id},
            )
            return [dict(r) for r in rows]
        except Exception as e:
            log_error(f"Error fetching form history: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_submission(employee_id: int, version_id: int):
        """Jawaban satu karyawan untuk satu periode; None bila belum mengisi."""
        try:
            # Yang diambil adalah pembaruan TERAKHIR.
            #
            # Tiap penyimpanan kini membuat baris baru, sehingga satu karyawan
            # dapat punya banyak baris untuk versi formulir yang sama. Tanpa
            # pengurutan, basis data bebas mengembalikan yang mana pun — dan
            # layar dapat menampilkan alamat lama sebagai keadaan sekarang.
            query = (
                select(employee_form_submissions_table)
                .where(
                    employee_form_submissions_table.c.employeeID == employee_id,
                    employee_form_submissions_table.c.versionID == version_id,
                    employee_form_submissions_table.c.isDelete == False,
                )
                .order_by(employee_form_submissions_table.c.submittedAt.desc())
                .limit(1)
            )
            row = await database.fetch_one(query)
            if row:
                return dict(row)

            # Belum pernah mengisi: jawaban awal DIISI dari data karyawan.
            #
            # Untuk karyawan lama, alamat dan telepon sudah tersimpan sejak
            # dulu di data pokoknya. Menampilkan formulir kosong membuat yang
            # mengisi mengetiknya ulang — dan yang diketik ulang kerap
            # berbeda dari yang sudah ada.
            #
            # Kategori pajak SENGAJA tidak diturunkan balik menjadi status
            # pernikahan: `K/2` tidak menyatakan siapa dua tanggungan itu,
            # dan menebaknya akan menuliskan keterangan yang tidak pernah
            # dinyatakan siapa pun.
            karyawan = await database.fetch_one(
                select(
                    employees_table.c.address,
                    employees_table.c.phoneNumber,
                    employees_table.c.email,
                ).where(employees_table.c.id == employee_id)
            )
            if not karyawan:
                return None

            awal = {}
            for kolom, kunci in (
                ("address", "currentAddress"),
                ("phoneNumber", "mobilePhone"),
                ("email", "personalEmail"),
            ):
                nilai = getattr(karyawan, kolom, None)
                if nilai:
                    awal[kunci] = nilai
            return {"answers": awal, "prefilled": True} if awal else None
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

            # Tiap penyimpanan membuat BARIS BARU, bukan menimpa.
            #
            # Pembaruan data karyawan dapat dilakukan kapan saja, dan yang
            # berlaku adalah yang terakhir. Menimpa baris lama menghapus
            # riwayatnya: alamat lama, jumlah tanggungan sebelumnya, dan
            # kapan tiap keadaan itu berlaku ikut hilang.
            #
            # Riwayat itu yang membuat "sudah setahun tidak diperbarui" dapat
            # dihitung sama sekali — tanpa baris per penyimpanan, tidak ada
            # tanggal yang dapat dibandingkan.
            #
            # Menyimpan ULANG tanpa mengubah apa pun tetap dicatat: yang
            # dikonfirmasi bukan datanya berubah, melainkan bahwa datanya
            # MASIH BENAR.
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

            # Data karyawan diselaraskan dari jawaban formulir.
            #
            # Kategori pajak, alamat, dan nomor telepon SEBELUMNYA diketik
            # dua kali: sekali di data karyawan, sekali di formulir ini.
            # Dua tempat untuk satu kenyataan berarti keduanya pasti akan
            # berbeda suatu saat — dan yang dipakai slip gaji adalah yang di
            # data karyawan, yang justru paling jarang disentuh.
            #
            # Sejak sekarang formulir ini yang menjadi sumbernya.
            perubahan = {}

            status_nikah = answers.get("maritalStatus")
            tanggungan = answers.get("dependents")
            if status_nikah is not None or tanggungan is not None:
                perubahan["taxCategory"] = kategori_pajak(
                    status_nikah, tanggungan
                )

            alamat = (answers.get("currentAddress") or "").strip()
            if alamat:
                perubahan["address"] = alamat[:255]

            hp = (answers.get("mobilePhone") or "").strip()
            if hp:
                perubahan["phoneNumber"] = hp[:30]

            surel = (answers.get("personalEmail") or "").strip()
            if surel:
                perubahan["email"] = surel[:100]

            if perubahan:
                # Nilai KOSONG tidak menimpa yang sudah ada: mengosongkan
                # satu isian pada formulir tidak berarti alamat karyawannya
                # hilang, hanya belum diisi ulang.
                perubahan["updatedAt"] = dt.now()
                perubahan["updatedBy"] = user_id
                await database.execute(
                    employees_table.update()
                    .where(employees_table.c.id == employee_id)
                    .values(**perubahan)
                )

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
