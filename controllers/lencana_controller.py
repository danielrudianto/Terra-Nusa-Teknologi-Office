"""Orkestrasi hitungan lencana menu samping."""

from utils.permission import _departments
from repository.lencana_repository import LencanaRepository


class LencanaController:
    @staticmethod
    async def semua(current_user: dict) -> dict:
        """
        Hitungan "menunggu saya" untuk pengguna yang sedang masuk.

        Level dan departemen diambil DI SINI, sekali, lalu diteruskan —
        bukan dibaca ulang di tiap hitungan. `_departments` sudah bercache,
        tetapi membacanya empat kali tetap berarti empat kali pemeriksaan
        kedaluwarsa cache untuk jawaban yang sama persis.
        """
        level = int(current_user.get("authenticationLevel") or 1)
        departemen = await _departments(current_user["id"])
        return await LencanaRepository.semua(current_user, level, departemen)
