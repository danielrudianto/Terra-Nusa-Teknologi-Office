from datetime import date as d
from datetime import timedelta

from repository.reminder_repository import BirthdayRepository, ReminderRepository
from utils.logger_utils import log_error

# Akses minimum untuk membuat pengingat bagi SELURUH pengguna.
#
# Bila terbuka untuk semua, agenda cepat penuh oleh hal yang hanya berlaku
# bagi satu-dua orang — dan begitu terlalu ramai, orang berhenti membacanya.
# Batas ini tidak menutup jalan: siapa pun tetap dapat menandai beberapa
# rekan sekaligus, hanya saja ia harus memilih siapa.
LEVEL_PENGINGAT_UMUM = 4


class AgendaController:
    @staticmethod
    async def agenda(user_id: int, hari_ini: d, jangkauan: int = 7):
        """
        Isi agenda: ulang tahun dan pengingat, dalam satu permintaan.

        Digabung karena keduanya selalu ditampilkan bersama; memisahkannya
        berarti layar menunggu dua jawaban untuk satu blok.
        """
        # Kedua bagian diambil terpisah, dan kegagalan salah satunya tidak
        # menjatuhkan yang lain.
        #
        # Sebelumnya satu galat membuat seluruh agenda gagal — pengguna
        # melihat "gagal memuat data" tanpa tahu bagian mana, dan ulang tahun
        # yang sebenarnya terbaca ikut hilang. Yang gagal cukup dikosongkan,
        # dan sebabnya dicatat di log agar dapat ditelusuri.
        ulang_tahun = []
        pengingat = []

        try:
            hasil = await BirthdayRepository.upcoming(hari_ini, jangkauan)
            if isinstance(hasil, dict) and "error" in hasil:
                log_error(f"Agenda: ulang tahun gagal dibaca: {hasil['error']}")
            else:
                ulang_tahun = hasil
        except Exception as e:
            log_error(f"Agenda: ulang tahun gagal dibaca: {type(e).__name__}: {e}")

        try:
            hasil = await ReminderRepository.get_range(
                user_id, hari_ini, hari_ini + timedelta(days=jangkauan)
            )
            if isinstance(hasil, dict) and "error" in hasil:
                log_error(f"Agenda: pengingat gagal dibaca: {hasil['error']}")
            else:
                pengingat = hasil
                for p in pengingat:
                    p["daysUntil"] = (p["date"] - hari_ini).days
        except Exception as e:
            log_error(f"Agenda: pengingat gagal dibaca: {type(e).__name__}: {e}")
            pengingat = []

        return {"birthdays": ulang_tahun, "reminders": pengingat}

    @staticmethod
    async def create(user_id: int, user_level: int, body):
        try:
            if body.isShared and int(user_level or 1) < LEVEL_PENGINGAT_UMUM:
                return {
                    "error": (
                        "Pengingat untuk seluruh pengguna hanya dapat dibuat "
                        "oleh akses 4 ke atas. Tandai rekan yang bersangkutan "
                        "bila hanya sebagian yang perlu tahu."
                    ),
                    "status": 403,
                }

            data = {
                "title": body.title.strip(),
                "note": (body.note or "").strip() or None,
                "date": body.date,
                "category": body.category,
                "isShared": bool(body.isShared),
                "createdBy": user_id,
            }
            # Pembuatnya selalu melihat pengingatnya sendiri; menandai diri
            # sendiri hanya menambah baris tanpa mengubah apa pun.
            targets = [t for t in (body.targets or []) if t != user_id]
            return await ReminderRepository.create(data, targets)
        except Exception as e:
            log_error(f"Error creating reminder: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update(user_id: int, user_level: int, reminder_id: int, body):
        try:
            lama = await ReminderRepository.get_by_id(reminder_id)
            if isinstance(lama, dict) and "error" in lama:
                return lama
            if not lama or lama.get("isDelete"):
                return {"error": "Reminder not found", "status": 404}

            # Hanya pembuatnya, berapa pun levelnya.
            #
            # Pengingat adalah catatan pribadi, bukan data perusahaan —
            # direktur pun tidak berkepentingan mengubah catatan orang lain.
            if lama.get("createdBy") != user_id:
                return {
                    "error": "Hanya pembuatnya yang dapat mengubah pengingat ini.",
                    "status": 403,
                }

            if body.isShared and int(user_level or 1) < LEVEL_PENGINGAT_UMUM:
                return {
                    "error": (
                        "Pengingat untuk seluruh pengguna hanya dapat dibuat "
                        "oleh akses 4 ke atas."
                    ),
                    "status": 403,
                }

            data = {}
            if body.title is not None:
                data["title"] = body.title.strip()
            if body.note is not None:
                data["note"] = body.note.strip() or None
            if body.date is not None:
                data["date"] = body.date
            if body.category is not None:
                data["category"] = body.category
            if body.isShared is not None:
                data["isShared"] = bool(body.isShared)

            targets = None
            if body.targets is not None:
                targets = [t for t in body.targets if t != user_id]

            return await ReminderRepository.update(reminder_id, data, targets)
        except Exception as e:
            log_error(f"Error updating reminder {reminder_id}: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def delete(user_id: int, reminder_id: int):
        try:
            lama = await ReminderRepository.get_by_id(reminder_id)
            if isinstance(lama, dict) and "error" in lama:
                return lama
            if not lama or lama.get("isDelete"):
                return {"error": "Reminder not found", "status": 404}

            if lama.get("createdBy") != user_id:
                return {
                    "error": "Hanya pembuatnya yang dapat menghapus pengingat ini.",
                    "status": 403,
                }

            return await ReminderRepository.soft_delete(reminder_id)
        except Exception as e:
            log_error(f"Error deleting reminder {reminder_id}: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
