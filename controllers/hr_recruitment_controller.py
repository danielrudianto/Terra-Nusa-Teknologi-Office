"""Lapis kendali modul rekrutmen."""

from repository.hr_recruitment_repository import HrRecruitmentRepository


class HrRecruitmentController:
    @staticmethod
    async def daftar_ujian():
        return await HrRecruitmentRepository.daftar_ujian()

    @staticmethod
    async def daftar_soal(test_id: int = None, keyword: str = None):
        return await HrRecruitmentRepository.daftar_soal(test_id, keyword)

    @staticmethod
    async def buat_soal(data: dict):
        return await HrRecruitmentRepository.buat_soal(data)

    @staticmethod
    async def ubah_soal(question_id: int, data: dict):
        return await HrRecruitmentRepository.ubah_soal(question_id, data)

    @staticmethod
    async def hapus_soal(question_id: int):
        return await HrRecruitmentRepository.hapus_soal(question_id)

    @staticmethod
    async def daftarkan_pelamar(
        test_id: int, orang: list, user_id: int, berlaku_hari: int = 7
    ):
        return await HrRecruitmentRepository.daftarkan_pelamar(
            test_id, orang, user_id, berlaku_hari
        )

    @staticmethod
    async def daftar_pelamar(test_id=None, status=None):
        return await HrRecruitmentRepository.daftar_pelamar(test_id, status)

    @staticmethod
    async def ubah_status_pelamar(candidate_id: int, status: str, user_id: int):
        return await HrRecruitmentRepository.ubah_status_pelamar(
            candidate_id, status, user_id
        )

    @staticmethod
    async def hapus_hasil(candidate_id: int, user_id: int):
        return await HrRecruitmentRepository.hapus_hasil(candidate_id, user_id)

    @staticmethod
    async def simpan_biodata(token: str, data: dict):
        return await HrRecruitmentRepository.simpan_biodata(token, data)

    @staticmethod
    async def buat_ujian(data: dict, user_id: int):
        return await HrRecruitmentRepository.buat_ujian(data, user_id)

    @staticmethod
    async def ubah_ujian(test_id: int, data: dict, user_id: int):
        return await HrRecruitmentRepository.ubah_ujian(
            test_id, data, user_id
        )

    @staticmethod
    async def lembar_jawaban(candidate_id: int):
        return await HrRecruitmentRepository.lembar_jawaban(candidate_id)

    @staticmethod
    async def nilai_jawaban(candidate_id: int, nilai: list, user_id: int):
        return await HrRecruitmentRepository.nilai_jawaban(
            candidate_id, nilai, user_id
        )

    @staticmethod
    async def pelamar_dari_token(token: str):
        return await HrRecruitmentRepository.pelamar_dari_token(token)

    @staticmethod
    async def mulai_ujian(token: str):
        return await HrRecruitmentRepository.mulai_ujian(token)

    @staticmethod
    async def simpan_jawaban(token: str, jawaban: dict):
        return await HrRecruitmentRepository.simpan_jawaban(token, jawaban)

    @staticmethod
    async def kirim_ujian(token: str, jawaban: dict = None):
        return await HrRecruitmentRepository.kirim_ujian(token, jawaban)
