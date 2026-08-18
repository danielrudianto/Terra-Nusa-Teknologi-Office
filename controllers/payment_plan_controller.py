from datetime import date
from typing import Any, Dict

from repository.payment_plan_repository import PaymentPlanRepository
from utils.logger_utils import log_info


class PaymentPlanController:
    @staticmethod
    async def buat(body: dict, user_id: int) -> Dict[str, Any]:
        hasil = await PaymentPlanRepository.buat(body, user_id)
        if "error" not in hasil:
            log_info(f"Rencana pengeluaran dibuat: {hasil.get('id')}")
        return hasil

    @staticmethod
    async def rentang(
        awal: date, akhir: date, project_name: str, sertakan_batal: bool
    ) -> Dict[str, Any]:
        data = await PaymentPlanRepository.rentang(
            awal, akhir, project_name, sertakan_batal
        )
        return {"data": data, "count": len(data)}

    @staticmethod
    async def ringkasan(awal: date, akhir: date) -> Dict[str, Any]:
        return await PaymentPlanRepository.ringkasan(awal, akhir)

    @staticmethod
    async def ubah(plan_id: int, body: dict, user_id: int) -> Dict[str, Any]:
        rencana = await PaymentPlanRepository.ambil(plan_id)
        if rencana is None:
            return {"error": "Rencana tidak ditemukan.", "status": 404}
        if "error" in rencana:
            return rencana

        # Yang SUDAH TERPAKAI tidak dapat diubah nilainya.
        #
        # Ia sudah dipakai membandingkan rencana dengan kenyataan; mengubahnya
        # setelah itu membuat selisihnya menyusut sendiri, dan yang meninjau
        # menyimpulkan perencanaannya lebih tepat daripada yang sebenarnya.
        #
        # Yang masih boleh: mengembalikannya ke `rencana` bila ternyata belum
        # terjadi, dan membatalkannya.
        if rencana["status"] == "terpakai":
            hanya_status = set(body.keys()) <= {"status"}
            if not hanya_status:
                return {
                    "error": (
                        "Rencana yang sudah ditandai terpakai tidak dapat "
                        "diubah nilainya."
                    ),
                    "status": 409,
                }

        return await PaymentPlanRepository.ubah(plan_id, body, user_id)

    @staticmethod
    async def hapus(plan_id: int, user_id: int) -> Dict[str, Any]:
        rencana = await PaymentPlanRepository.ambil(plan_id)
        if rencana is None:
            return {"error": "Rencana tidak ditemukan.", "status": 404}
        if "error" in rencana:
            return rencana

        # Yang sudah terpakai DIBATALKAN, bukan dihapus.
        #
        # Ia bagian dari riwayat perencanaan: selisih antara yang direncanakan
        # dan yang terjadi justru yang menjelaskan mengapa kasnya meleset, dan
        # itu hilang bila barisnya lenyap.
        if rencana["status"] == "terpakai":
            return {
                "error": (
                    "Rencana yang sudah terpakai tidak dapat dihapus. "
                    "Batalkan bila memang tidak jadi."
                ),
                "status": 409,
            }

        return await PaymentPlanRepository.hapus(plan_id, user_id)
