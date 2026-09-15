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
        # `current_user` adalah `databases.Record`, BUKAN dict.
        #
        # Record TIDAK punya `.get()` — memanggilnya melempar AttributeError,
        # dan galat yang tidak tertangkap itu keluar lewat lapisan TERLUAR
        # Starlette, di luar CORSMiddleware. Jawabannya karena itu sampai ke
        # peramban TANPA header CORS, dan yang terbaca di konsol bukan "500"
        # melainkan "No 'Access-Control-Allow-Origin' header is present" —
        # menunjuk ke arah yang sama sekali salah.
        #
        # Sudah tercatat di CLAUDE.md; saya tetap melanggarnya.
        level = int(current_user["authenticationLevel"] or 1)
        departemen = await _departments(current_user["id"])
        return await LencanaRepository.semua(current_user, level, departemen)
