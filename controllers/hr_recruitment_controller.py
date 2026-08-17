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
