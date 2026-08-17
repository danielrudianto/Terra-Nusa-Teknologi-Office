import secrets
from datetime import datetime as dt, timedelta

from sqlalchemy import insert, select, update

from constants.employee_form_default import FORMULIR_BAWAAN, periksa_definisi
from models.employee_form_model import (
    employee_form_submissions_table,
    employee_form_versions_table,
    employee_form_invites_table,
)
from models.employee_model import employees_table
from models.user_model import users_table
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




def _baca_jawaban(v):
    """
    Baca kolom `answers`, apa pun bentuk penyimpanannya.

    Baris LAMA tersandi dua kali — akibat `json.dumps` yang dipanggil sebelum
    SQLAlchemy menyandikannya lagi — sehingga membacanya sekali menghasilkan
    string, bukan objek. Layar yang menerimanya menampilkan "0 isian" tanpa
    satu pun galat.

    Membaca berulang sampai menjadi objek membuat baris lama tetap terbaca
    tanpa perlu memperbaiki datanya lebih dulu; baris baru sudah tersimpan
    benar dan berhenti pada putaran pertama.
    """
    import json as _json

    for _ in range(3):
        if isinstance(v, (dict, list)):
            return v
        if not isinstance(v, str):
            return {}
        try:
            v = _json.loads(v)
        except (ValueError, TypeError):
            return {}
    return v if isinstance(v, (dict, list)) else {}

def _siap_json(v):
    """
    Ubah nilai yang tidak dikenal JSON menjadi teks, tanpa menyandikannya.

    `json.dumps(..., default=str)` sebelumnya menangani tanggal dan Decimal
    sekaligus. Karena penyandiannya kini diserahkan kepada SQLAlchemy,
    pengubahan itu perlu dilakukan tersendiri — tanpa itu, satu tanggal di
    dalam jawaban membuat seluruh penyimpanan gagal.
    """
    if isinstance(v, dict):
        return {k: _siap_json(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_siap_json(x) for x in v]
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


class EmployeeFormRepository:
    """
    Formulir keadaan karyawan yang ditanyakan berkala.

    Pertanyaannya disimpan bersama jawabannya lewat `versionID`: jawaban
    2026 selalu dibaca dengan pertanyaan 2026, walaupun formulir 2027 sudah
    berbeda.
    """

    # ---------------------------------------------------------------- versi

    @staticmethod
    async def buat_undangan(employee_id: int, version_id: int, user_id: int):
        """
        Terbitkan tautan pengisian untuk satu karyawan.

        Undangan lama yang masih berlaku DIHAPUS lebih dulu. Dua tautan aktif
        untuk orang yang sama berarti yang menerimanya harus menebak mana yang
        masih hidup — dan yang salah tebak menyimpulkan tautannya rusak.
        """
        try:
            await database.execute(
                update(employee_form_invites_table)
                .where(employee_form_invites_table.c.employeeID == employee_id)
                .where(employee_form_invites_table.c.isDelete == False)
                .values(isDelete=True)
            )

            # 32 byte acak; menebaknya tidak mungkin dalam praktik.
            token = secrets.token_urlsafe(32)
            sekarang = dt.now()

            invite_id = await database.execute(
                insert(employee_form_invites_table).values(
                    employeeID=employee_id,
                    versionID=version_id,
                    token=token,
                    # Tiga hari: cukup untuk mengisi, tidak cukup untuk
                    # terlupakan di riwayat pesan.
                    expiresAt=sekarang + timedelta(days=3),
                    createdAt=sekarang,
                    createdBy=user_id,
                )
            )
            return {"id": invite_id, "token": token,
                    "expiresAt": sekarang + timedelta(days=3)}
        except Exception as e:
            log_error(f"Error creating form invite: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def undangan_dari_token(token: str):
        """
        Baca undangan dari tokennya.

        Mengembalikan `None` bila tokennya tidak dikenal, sudah dicabut, atau
        sudah lewat masa berlakunya — ketiganya diperlakukan sama, dan
        pemanggil menjawab dengan pesan yang sama pula. Membedakannya
        memberi tahu penebak bahwa tokennya PERNAH ada.
        """
        try:
            baris = await database.fetch_one(
                select(
                    employee_form_invites_table.c.id,
                    employee_form_invites_table.c.employeeID,
                    employee_form_invites_table.c.versionID,
                    employee_form_invites_table.c.expiresAt,
                    employee_form_invites_table.c.createdBy,
                    employees_table.c.name,
                    users_table.c.name.label("pengundang"),
                )
                .select_from(
                    employee_form_invites_table.join(
                        employees_table,
                        employee_form_invites_table.c.employeeID
                        == employees_table.c.id,
                    ).outerjoin(
                        users_table,
                        employee_form_invites_table.c.createdBy
                        == users_table.c.id,
                    )
                )
                .where(employee_form_invites_table.c.token == token)
                .where(employee_form_invites_table.c.isDelete == False)
                .where(employee_form_invites_table.c.expiresAt > dt.now())
                .where(employees_table.c.isDelete == False)
            )
            if baris is None:
                return None
            return {
                "id": baris["id"],
                "employeeID": baris["employeeID"],
                "versionID": baris["versionID"],
                "expiresAt": baris["expiresAt"],
                "createdBy": baris["createdBy"],
                "employeeName": baris["name"],
                # Nama yang meminta, ditampilkan pada halaman pengisian.
                #
                # Yang menerima tautan lewat surel perlu tahu dari siapa
                # permintaannya datang — tautan tanpa asal yang jelas
                # tampak seperti percobaan penipuan, dan yang berhati-hati
                # justru tidak mengisinya.
                "pengundang": baris["pengundang"],
            }
        except Exception as e:
            log_error(f"Error reading form invite: {str(e)}")
            return None

    @staticmethod
    async def tandai_terpakai(invite_id: int):
        """Catat waktu pengisian terakhir; tokennya tetap berlaku."""
        try:
            await database.execute(
                update(employee_form_invites_table)
                .where(employee_form_invites_table.c.id == invite_id)
                .values(usedAt=dt.now())
            )
        except Exception as e:
            log_error(f"Error marking invite used: {str(e)}")

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
                d = dict(row)
            # `fields` dibaca lewat pembaca yang sama: baris lama tersandi
            # dua kali dan tanpa ini terbaca sebagai teks, sehingga label
            # pertanyaan tidak pernah sampai ke layar.
            d["fields"] = _baca_jawaban(d.get("fields"))
            return d

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
                    # Kolomnya bertipe JSON; SQLAlchemy menyandikannya
                    # sendiri. Menyandikan lebih dulu membuat isinya tersandi
                    # DUA KALI, dan pembacanya menerima teks yang tidak punya
                    # satu pun kunci.
                    fields=_siap_json(FORMULIR_BAWAAN),
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
                "fields": _siap_json(definisi),
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
            # Jawaban dibaca lewat `_baca_jawaban`: baris lama tersandi
            # dua kali dan tanpa ini terbaca sebagai teks, bukan objek.
            hasil = []
            for r in rows:
                d = dict(r)
                d["answers"] = _baca_jawaban(d.get("answers"))
                hasil.append(d)
            return hasil
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
                d = dict(row)
                d["answers"] = _baca_jawaban(d.get("answers"))
                return d

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
                    # Diserahkan APA ADANYA, bukan di-`json.dumps` dulu.
                    #
                    # Kolomnya bertipe JSON, sehingga SQLAlchemy sudah
                    # menyandikannya sendiri. Menyandikannya lebih dulu
                    # membuat isinya tersandi DUA KALI — yang tersimpan
                    # menjadi string berisi JSON, bukan objek — dan
                    # pembacanya menerima teks yang tampak benar tetapi tidak
                    # punya satu pun kunci.
                    #
                    # `default=str` yang hilang digantikan `_siap_json` di
                    # bawah: tanggal dan Decimal tetap perlu diubah menjadi
                    # teks sebelum diserahkan.
                    answers=_siap_json(answers),
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
