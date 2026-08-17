"""
Bank soal ujian rekrutmen.

Soalnya esai dan dinilai orang; tidak ada kunci jawaban di sini. Yang disimpan
hanya pertanyaan, catatan, lampiran, dan nilai maksimalnya.
"""

import secrets
from datetime import datetime as dt, timedelta

from sqlalchemy import func, insert, select, update

from models.hr_recruitment_model import (
    hr_answers_table,
    hr_candidates_table,
    hr_questions_table,
    hr_tests_table,
)
from utils.database import database
from utils.logger_utils import log_error


class HrRecruitmentRepository:
    # ------------------------------------------------------------ paket ujian

    # ------------------------------------------------------- ujian (publik)

    @staticmethod
    async def pelamar_dari_token(token: str):
        """
        Baca pelamar dari tokennya, untuk halaman ujian.

        Mengembalikan `None` bila tokennya tidak dikenal, sudah dihapus, atau
        lewat masa berlakunya — ketiganya diperlakukan sama, dan pemanggil
        menjawab dengan pesan yang sama pula. Membedakannya memberi tahu
        penebak bahwa tokennya PERNAH ada.
        """
        try:
            baris = await database.fetch_one(
                select(
                    hr_candidates_table.c.id,
                    hr_candidates_table.c.name,
                    hr_candidates_table.c.gender,
                    hr_candidates_table.c.testID,
                    hr_candidates_table.c.expiresAt,
                    hr_candidates_table.c.startedAt,
                    hr_candidates_table.c.submittedAt,
                    hr_candidates_table.c.status,
                    hr_tests_table.c.name.label("testName"),
                    hr_tests_table.c.description.label("testDescription"),
                    hr_tests_table.c.durationMinutes,
                )
                .select_from(
                    hr_candidates_table.join(
                        hr_tests_table,
                        hr_candidates_table.c.testID == hr_tests_table.c.id,
                    )
                )
                .where(hr_candidates_table.c.token == token)
                .where(hr_candidates_table.c.isDelete == False)  # noqa: E712
                .where(hr_candidates_table.c.expiresAt > dt.now())
            )
            if baris is None:
                return None

            jumlah = await database.fetch_val(
                select(func.count()).where(
                    hr_questions_table.c.testID == baris["testID"],
                    hr_questions_table.c.isDelete == False,  # noqa: E712
                )
            )

            return {
                "name": baris["name"],
                "gender": baris["gender"],
                "testName": baris["testName"],
                "testDescription": baris["testDescription"],
                "durationMinutes": baris["durationMinutes"],
                "jumlahSoal": int(jumlah or 0),
                "expiresAt": baris["expiresAt"],
                "startedAt": baris["startedAt"],
                "submittedAt": baris["submittedAt"],
                "status": baris["status"],
                # `id` TIDAK dikembalikan.
                #
                # Halaman ujian tidak memerlukannya — seluruh rutenya
                # menerima token, bukan id — dan nomor pelamar adalah
                # keterangan yang tidak perlu diberikan kepada yang
                # mengerjakan.
            }
        except Exception as e:
            log_error(f"Error reading candidate by token: {str(e)}")
            return None

    @staticmethod
    async def mulai_ujian(token: str):
        """
        Tandai pesertanya MULAI, lalu kembalikan soalnya.

        Waktu mulai dicatat DI SINI, bukan dikirim layar. Waktu dari layar
        dapat diubah siapa pun yang membuka DevTools — dan ujian yang
        timernya dapat diatur peserta tidak mengukur apa pun.

        Bila sudah pernah mulai, `startedAt` TIDAK ditimpa: menutup peramban
        lalu membukanya kembali tidak memberi tambahan waktu. Itu justru
        celah yang paling mudah ditemukan sendiri.
        """
        try:
            baris = await database.fetch_one(
                select(
                    hr_candidates_table.c.id,
                    hr_candidates_table.c.testID,
                    hr_candidates_table.c.startedAt,
                    hr_candidates_table.c.submittedAt,
                    hr_tests_table.c.durationMinutes,
                )
                .select_from(
                    hr_candidates_table.join(
                        hr_tests_table,
                        hr_candidates_table.c.testID == hr_tests_table.c.id,
                    )
                )
                .where(hr_candidates_table.c.token == token)
                .where(hr_candidates_table.c.isDelete == False)  # noqa: E712
                .where(hr_candidates_table.c.expiresAt > dt.now())
            )
            if baris is None:
                return None

            if baris["submittedAt"]:
                return {"error": "Ujian sudah dikirim.", "status": 409}

            mulai = baris["startedAt"]
            if not mulai:
                mulai = dt.now()
                await database.execute(
                    update(hr_candidates_table)
                    .where(hr_candidates_table.c.id == baris["id"])
                    .values(startedAt=mulai, status="mengerjakan")
                )

            durasi = int(baris["durationMinutes"] or 90)
            batas = mulai + timedelta(minutes=durasi)
            sisa = int((batas - dt.now()).total_seconds())

            soal = await database.fetch_all(
                select(
                    hr_questions_table.c.id,
                    hr_questions_table.c.sortOrder,
                    hr_questions_table.c.question,
                    hr_questions_table.c.notes,
                    hr_questions_table.c.attachment,
                    hr_questions_table.c.category,
                    hr_questions_table.c.maxScore,
                    hr_questions_table.c.allowsUpload,
                )
                .where(hr_questions_table.c.testID == baris["testID"])
                .where(hr_questions_table.c.isDelete == False)  # noqa: E712
                .order_by(hr_questions_table.c.sortOrder)
            )

            jawaban = await database.fetch_all(
                select(
                    hr_answers_table.c.questionID,
                    hr_answers_table.c.answer,
                ).where(hr_answers_table.c.candidateID == baris["id"])
            )

            return {
                "startedAt": mulai,
                # Sisa waktu dalam DETIK, dihitung server.
                #
                # Layar menampilkan hitungan mundurnya sendiri, tetapi yang
                # menentukan tetap angka ini — ia diperiksa ulang setiap kali
                # jawaban disimpan.
                "sisaDetik": max(sisa, 0),
                "durationMinutes": durasi,
                "questions": [dict(r) for r in soal],
                "answers": {
                    str(r["questionID"]): r["answer"] for r in jawaban
                },
            }
        except Exception as e:
            log_error(f"Error starting exam: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def sisa_waktu(candidate_id: int):
        """
        Sisa waktu dalam detik; negatif berarti sudah lewat.

        Dihitung ulang dari basis data setiap kali, bukan disimpan — nilai
        yang disimpan akan basi begitu ada yang menyentuh jam sistemnya.
        """
        baris = await database.fetch_one(
            select(
                hr_candidates_table.c.startedAt,
                hr_tests_table.c.durationMinutes,
            )
            .select_from(
                hr_candidates_table.join(
                    hr_tests_table,
                    hr_candidates_table.c.testID == hr_tests_table.c.id,
                )
            )
            .where(hr_candidates_table.c.id == candidate_id)
        )
        if baris is None or not baris["startedAt"]:
            return None
        batas = baris["startedAt"] + timedelta(
            minutes=int(baris["durationMinutes"] or 90)
        )
        return int((batas - dt.now()).total_seconds())

    @staticmethod
    async def simpan_jawaban(token: str, jawaban: dict):
        """
        Simpan jawaban yang sedang dikerjakan.

        Dipanggil berkala oleh layar, bukan hanya saat mengirim: koneksi di
        rumah pelamar kerap putus, dan kehilangan satu jam pengerjaan karena
        satu kali putus adalah kegagalan yang tidak dapat diperbaiki
        sesudahnya.

        Waktu diperiksa DI SINI juga. Layar boleh saja tetap terbuka setelah
        timernya habis — yang menentukan adalah jam server.
        """
        try:
            pelamar = await database.fetch_one(
                select(
                    hr_candidates_table.c.id,
                    hr_candidates_table.c.testID,
                    hr_candidates_table.c.submittedAt,
                )
                .where(hr_candidates_table.c.token == token)
                .where(hr_candidates_table.c.isDelete == False)  # noqa: E712
                .where(hr_candidates_table.c.expiresAt > dt.now())
            )
            if pelamar is None:
                return None
            if pelamar["submittedAt"]:
                return {"error": "Ujian sudah dikirim.", "status": 409}

            sisa = await HrRecruitmentRepository.sisa_waktu(pelamar["id"])
            if sisa is None:
                return {"error": "Ujian belum dimulai.", "status": 400}
            if sisa <= 0:
                return {"error": "Waktu pengerjaan sudah habis.", "status": 410}

            # Hanya soal MILIK paket ujiannya yang diterima.
            #
            # Muatan dapat disusun sendiri oleh siapa pun; tanpa penyaringan
            # ini, jawaban dapat ditulis ke soal paket lain — dan lembar
            # jawaban pelamar lain ikut tersentuh.
            sah = {
                r["id"]
                for r in await database.fetch_all(
                    select(hr_questions_table.c.id)
                    .where(hr_questions_table.c.testID == pelamar["testID"])
                    .where(hr_questions_table.c.isDelete == False)  # noqa: E712
                )
            }

            sekarang = dt.now()
            for kunci, isi in (jawaban or {}).items():
                try:
                    qid = int(kunci)
                except (TypeError, ValueError):
                    continue
                if qid not in sah:
                    continue

                ada = await database.fetch_val(
                    select(hr_answers_table.c.id)
                    .where(hr_answers_table.c.candidateID == pelamar["id"])
                    .where(hr_answers_table.c.questionID == qid)
                )
                if ada:
                    await database.execute(
                        update(hr_answers_table)
                        .where(hr_answers_table.c.id == ada)
                        .values(answer=isi, updatedAt=sekarang)
                    )
                else:
                    await database.execute(
                        insert(hr_answers_table).values(
                            candidateID=pelamar["id"],
                            questionID=qid,
                            answer=isi,
                            updatedAt=sekarang,
                        )
                    )

            return {"tersimpan": True, "sisaDetik": sisa}
        except Exception as e:
            log_error(f"Error saving exam answers: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def kirim_ujian(token: str, jawaban: dict = None):
        """
        Kirim jawaban akhir; setelah ini tidak dapat disunting lagi.

        Jawaban terakhir ikut disimpan lebih dulu — yang menekan Kirim kerap
        baru saja mengetik sesuatu, dan menyimpannya terpisah membuat ketikan
        terakhir hilang.
        """
        try:
            if jawaban:
                hasil = await HrRecruitmentRepository.simpan_jawaban(
                    token, jawaban
                )
                # Waktu habis tidak menghalangi pengiriman: yang sudah
                # tersimpan tetap dikirim, dan penilailah yang memutuskan.
                if isinstance(hasil, dict) and hasil.get("status") == 500:
                    return hasil

            pelamar = await database.fetch_one(
                select(
                    hr_candidates_table.c.id,
                    hr_candidates_table.c.submittedAt,
                )
                .where(hr_candidates_table.c.token == token)
                .where(hr_candidates_table.c.isDelete == False)  # noqa: E712
            )
            if pelamar is None:
                return None
            if pelamar["submittedAt"]:
                return {"error": "Ujian sudah dikirim.", "status": 409}

            await database.execute(
                update(hr_candidates_table)
                .where(hr_candidates_table.c.id == pelamar["id"])
                .values(submittedAt=dt.now(), status="selesai")
            )
            return {"terkirim": True}
        except Exception as e:
            log_error(f"Error submitting exam: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

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
