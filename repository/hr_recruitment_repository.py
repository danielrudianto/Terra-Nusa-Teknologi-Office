"""
Bank soal ujian rekrutmen.

Soalnya esai dan dinilai orang; tidak ada kunci jawaban di sini. Yang disimpan
hanya pertanyaan, catatan, lampiran, dan nilai maksimalnya.
"""

import secrets
from datetime import datetime as dt, timedelta

from sqlalchemy import func, insert, select, update

from models.hr_recruitment_model import (
    hr_candidates_table,
    hr_questions_table,
    hr_tests_table,
)
from utils.database import database
from utils.logger_utils import log_error


class HrRecruitmentRepository:
    # ------------------------------------------------------------ paket ujian

    # -------------------------------------------------------------- pelamar

    @staticmethod
    async def daftarkan_pelamar(
        test_id: int, orang: list[dict], user_id: int, berlaku_hari: int = 7
    ):
        """
        Daftarkan beberapa pelamar sekaligus, masing-masing dengan tokennya.

        Yang diminta hanya nama dan jenis kelamin. Sisanya — panggilan,
        tanggal lahir, alamat, kontak — diisi pelamar sendiri lewat tautan;
        mengumpulkannya lebih dulu justru pekerjaan yang hendak dihilangkan.

        Berlaku tujuh hari, bukan tiga seperti formulir karyawan: pelamar
        belum terikat apa pun pada perusahaan, dan yang sedang mencari kerja
        kerap baru membuka surel di akhir pekan.
        """
        try:
            sekarang = dt.now()
            kedaluwarsa = sekarang + timedelta(days=berlaku_hari)

            hasil = []
            for o in orang:
                nama = str(o.get("name") or "").strip()
                if not nama:
                    # Baris kosong dilewati diam-diam.
                    #
                    # Menempel daftar nama kerap membawa baris kosong di
                    # ujungnya, dan menolak seluruh permintaan karenanya
                    # memaksa yang menempelnya merapikan dulu.
                    continue

                jk = str(o.get("gender") or "").strip().upper()[:1]
                token = secrets.token_urlsafe(32)

                pelamar_id = await database.execute(
                    insert(hr_candidates_table).values(
                        testID=test_id,
                        name=nama,
                        gender=jk if jk in ("L", "P") else None,
                        token=token,
                        expiresAt=kedaluwarsa,
                        status="baru",
                        createdAt=sekarang,
                        createdBy=user_id,
                    )
                )
                hasil.append(
                    {
                        "id": pelamar_id,
                        "name": nama,
                        "gender": jk if jk in ("L", "P") else None,
                        "token": token,
                        "expiresAt": kedaluwarsa,
                    }
                )

            return {"dibuat": len(hasil), "pelamar": hasil}
        except Exception as e:
            log_error(f"Error registering candidates: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def daftar_pelamar(test_id: int = None, status: str = None):
        """Pelamar beserta paket ujiannya."""
        try:
            syarat = [hr_candidates_table.c.isDelete == False]  # noqa: E712
            if test_id:
                syarat.append(hr_candidates_table.c.testID == test_id)
            if status:
                syarat.append(hr_candidates_table.c.status == status)

            baris = await database.fetch_all(
                select(
                    hr_candidates_table.c.id,
                    hr_candidates_table.c.testID,
                    hr_candidates_table.c.name,
                    hr_candidates_table.c.gender,
                    hr_candidates_table.c.email,
                    hr_candidates_table.c.phoneNumber,
                    hr_candidates_table.c.token,
                    hr_candidates_table.c.expiresAt,
                    hr_candidates_table.c.startedAt,
                    hr_candidates_table.c.submittedAt,
                    hr_candidates_table.c.status,
                    hr_candidates_table.c.createdAt,
                    hr_tests_table.c.name.label("testName"),
                )
                .select_from(
                    hr_candidates_table.join(
                        hr_tests_table,
                        hr_candidates_table.c.testID == hr_tests_table.c.id,
                    )
                )
                .where(*syarat)
                .order_by(hr_candidates_table.c.id.desc())
            )
            return [dict(r) for r in baris]
        except Exception as e:
            log_error(f"Error listing candidates: {str(e)}")
            return {"error": "Internal server error.", "status": 500}


    @staticmethod
    async def daftar_ujian():
        """
        Seluruh paket ujian beserta jumlah soalnya.

        Jumlah soal dihitung di sini, bukan di layar: menghitungnya di layar
        menuntut seluruh soal ikut dikirim, dan tujuh puluh lima pertanyaan
        esai jauh lebih besar daripada daftar yang hendak ditampilkan.
        """
        try:
            baris = await database.fetch_all(
                select(
                    hr_tests_table.c.id,
                    hr_tests_table.c.name,
                    hr_tests_table.c.description,
                    hr_tests_table.c.durationMinutes,
                    hr_tests_table.c.isActive,
                    func.count(hr_questions_table.c.id).label("jumlahSoal"),
                )
                .select_from(
                    hr_tests_table.outerjoin(
                        hr_questions_table,
                        (hr_questions_table.c.testID == hr_tests_table.c.id)
                        & (hr_questions_table.c.isDelete == False),  # noqa: E712
                    )
                )
                .where(hr_tests_table.c.isDelete == False)  # noqa: E712
                .group_by(
                    hr_tests_table.c.id,
                    hr_tests_table.c.name,
                    hr_tests_table.c.description,
                    hr_tests_table.c.durationMinutes,
                    hr_tests_table.c.isActive,
                )
                .order_by(hr_tests_table.c.name)
            )
            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "description": r["description"],
                    "durationMinutes": r["durationMinutes"],
                    "isActive": bool(r["isActive"]),
                    "jumlahSoal": int(r["jumlahSoal"] or 0),
                }
                for r in baris
            ]
        except Exception as e:
            log_error(f"Error listing hr tests: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    # ----------------------------------------------------------------- soal

    @staticmethod
    async def daftar_soal(test_id: int = None, keyword: str = None):
        """
        Soal, disaring paket ujian dan kata pencarian.

        Pencarian menyentuh pertanyaan DAN catatannya: sebagian soal hanya
        dapat ditemukan lewat standar yang disebut di catatannya — "SNI-03"
        tidak muncul di pertanyaannya sama sekali.
        """
        try:
            syarat = [hr_questions_table.c.isDelete == False]  # noqa: E712
            if test_id:
                syarat.append(hr_questions_table.c.testID == test_id)
            if keyword:
                pola = f"%{keyword}%"
                syarat.append(
                    hr_questions_table.c.question.ilike(pola)
                    | hr_questions_table.c.notes.ilike(pola)
                )

            baris = await database.fetch_all(
                select(
                    hr_questions_table.c.id,
                    hr_questions_table.c.testID,
                    hr_questions_table.c.sortOrder,
                    hr_questions_table.c.question,
                    hr_questions_table.c.notes,
                    hr_questions_table.c.attachment,
                    hr_questions_table.c.category,
                    hr_questions_table.c.maxScore,
                    hr_questions_table.c.allowsUpload,
                    hr_tests_table.c.name.label("testName"),
                )
                .select_from(
                    hr_questions_table.join(
                        hr_tests_table,
                        hr_questions_table.c.testID == hr_tests_table.c.id,
                    )
                )
                .where(*syarat)
                .order_by(
                    hr_questions_table.c.testID,
                    hr_questions_table.c.sortOrder,
                )
            )
            return [dict(r) for r in baris]
        except Exception as e:
            log_error(f"Error listing hr questions: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def buat_soal(data: dict):
        """
        Tambah satu soal ke paket ujian.

        Urutannya diisi otomatis di belakang yang sudah ada; yang membuat soal
        memikirkan isinya, bukan nomor ke berapa ia muncul.
        """
        try:
            terakhir = await database.fetch_val(
                select(func.max(hr_questions_table.c.sortOrder)).where(
                    hr_questions_table.c.testID == data["testID"]
                )
            )

            soal_id = await database.execute(
                insert(hr_questions_table).values(
                    testID=data["testID"],
                    sortOrder=int(terakhir or 0) + 1,
                    question=data["question"],
                    notes=data.get("notes") or None,
                    attachment=data.get("attachment") or None,
                    category=data.get("category") or "civil",
                    maxScore=int(data.get("maxScore") or 5),
                    allowsUpload=bool(data.get("allowsUpload")),
                    # `createdAt` diisi manual.
                    #
                    # Default kolom sisi-Python tidak pernah berlaku pada
                    # pustaka `databases`: kueri yang dieksekusi sudah
                    # terkompilasi, sehingga langkah itu dilewati dan nilainya
                    # sampai ke MySQL sebagai NULL.
                    createdAt=dt.now(),
                )
            )
            return {"id": soal_id}
        except Exception as e:
            log_error(f"Error creating hr question: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def ubah_soal(question_id: int, data: dict):
        """Ubah satu soal; hanya kolom yang dikirim yang tersentuh."""
        try:
            boleh = (
                "question",
                "notes",
                "attachment",
                "category",
                "maxScore",
                "allowsUpload",
                "sortOrder",
            )
            nilai = {k: data[k] for k in boleh if k in data}
            if not nilai:
                return {"id": question_id}

            await database.execute(
                update(hr_questions_table)
                .where(hr_questions_table.c.id == question_id)
                .values(**nilai)
            )
            return {"id": question_id}
        except Exception as e:
            log_error(f"Error updating hr question: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def hapus_soal(question_id: int):
        """
        Tandai soal terhapus; barisnya tetap ada.

        Jawaban lama menunjuk ke soal ini. Menghapus barisnya membuat lembar
        jawaban pelamar yang sudah dinilai kehilangan pertanyaannya — dan
        nilai tanpa pertanyaan tidak dapat ditinjau ulang oleh siapa pun.
        """
        try:
            await database.execute(
                update(hr_questions_table)
                .where(hr_questions_table.c.id == question_id)
                .values(isDelete=True)
            )
            return {"id": question_id}
        except Exception as e:
            log_error(f"Error deleting hr question: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
