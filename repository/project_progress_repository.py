"""
Baca-tulis kemajuan proyek.

Seluruh kueri tabel `project_progress` ada di sini; controller tidak menyentuh
basis data sendiri.
"""

from datetime import date as d, datetime as dt
from decimal import Decimal, ROUND_HALF_UP

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
    async def skalakan(
        project_id: int,
        dpp_lama,
        dpp_baru,
        userID: int,
        sebab: str,
    ) -> dict:
        """
        Susun ulang persen kemajuan setelah NILAI KONTRAK berubah.

        MENGAPA PERLU

        Kemajuan disimpan sebagai PERSEN, sedangkan yang tidak berubah saat
        adendum terbit adalah pekerjaan yang sudah dikerjakan. Persen adalah
        pekerjaan itu dibagi nilai kontrak — jadi begitu penyebutnya berganti,
        seluruh angka lama menyatakan hal yang berbeda dari yang dimaksud
        ketika dicatat.

        Kontrak 100 dengan kemajuan 5% berarti pekerjaan senilai 5. Kontrak
        dipangkas menjadi 50 lewat adendum; pekerjaan yang sama sekarang
        separuh dari lingkup yang tersisa:

            5% x (100 / 50) = 10%

        Bukan 2,5%. Yang dikalikan adalah PERBANDINGAN TERBALIKNYA, karena
        yang tetap adalah pembilangnya. Kontrak yang MEMBESAR menurunkan
        persennya dengan aturan yang sama — pekerjaan yang sama menjadi
        bagian yang lebih kecil dari lingkup yang lebih besar.

        Tanpa penyesuaian ini, kurva S membandingkan kemajuan terhadap
        kontrak baru dengan biaya terhadap kontrak baru, sementara angka
        kemajuannya masih mengukur kontrak lama. Keduanya tetap tergambar
        rapi, dan selisihnya terbaca sebagai kemajuan yang melesat atau
        tertinggal — padahal tidak satu pun pekerjaan berubah.

        YANG SENGAJA TIDAK DILAKUKAN

        Hasilnya TIDAK dibatasi 100%. Lingkup yang dipangkas di bawah
        pekerjaan yang sudah terlanjur dikerjakan memang menghasilkan angka
        di atas seratus, dan itu keadaan yang justru paling perlu terlihat:
        kontraknya tidak lagi menutup pekerjaan yang sudah jadi. Dibatasi
        seratus, keadaan itu terbaca persis seperti proyek yang selesai
        tepat waktu.
        """
        try:
            lama = Decimal(str(dpp_lama or 0))
            baru = Decimal(str(dpp_baru or 0))

            # Tidak ada yang dapat dihitung: pembagian terhadap nol, atau
            # perbandingan terhadap kontrak yang dahulu belum ada. Kemajuan
            # dibiarkan apa adanya — angka lama yang salah lebih baik
            # daripada angka baru yang dikarang.
            if lama <= 0 or baru <= 0 or lama == baru:
                return {"disesuaikan": 0}

            baris = await database.fetch_all(
                select(project_progress_table).where(
                    project_progress_table.c.projectID == project_id,
                    project_progress_table.c.isDelete == False,  # noqa: E712
                )
            )
            if not baris:
                return {"disesuaikan": 0}

            from repository.audit_log_repository import AuditLogRepository

            jumlah = 0
            for b in baris:
                persen_lama = Decimal(str(b["percentage"]))
                persen_baru = (persen_lama * lama / baru).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if persen_baru == persen_lama:
                    continue

                await database.execute(
                    project_progress_table.update()
                    .where(project_progress_table.c.id == b["id"])
                    .values(
                        percentage=persen_baru,
                        updatedAt=dt.now(),
                        updatedBy=userID,
                    )
                )

                # Aksinya DIBEDAKAN dari `update`.
                #
                # Yang membaca riwayat harus dapat melihat bahwa angkanya
                # disusun ulang oleh sistem karena kontraknya berubah, bukan
                # diketik ulang seseorang. Keduanya terlihat persis sama pada
                # jejak bila memakai aksi yang sama, dan yang menelusurinya
                # setahun kemudian akan mencari orang yang mengubahnya.
                #
                # `userID` TETAP orang yang menerbitkan adendumnya: sistem
                # tidak bertindak sendiri, ia menindaklanjuti perbuatan
                # seseorang, dan jejak yang kehilangan orang itu kehilangan
                # pertanggungjawabannya.
                await AuditLogRepository.record(
                    entity="project_progress",
                    entityID=int(b["id"]),
                    action="progress_rebase",
                    userID=userID,
                    changes={
                        "percentage": {
                            "from": str(persen_lama),
                            "to": str(persen_baru),
                        }
                    },
                    note=(
                        f"Disesuaikan sistem: nilai kontrak {lama} -> {baru}"
                        f" ({sebab})".strip()
                    ),
                )
                jumlah += 1

            return {"disesuaikan": jumlah}
        except Exception as e:
            log_error(
                f"Error rescaling progress for project {project_id}: {str(e)}"
            )
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
