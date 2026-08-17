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
