from datetime import date as d, timedelta
from typing import List

from sqlalchemy import and_, delete, insert, or_, select, update

from models.employee_model import employees_table
from models.reminder_model import reminder_targets_table, reminders_table
from models.user_model import users_table
from utils.database import database
from utils.logger_utils import log_error
from utils.errors import internal_error


class ReminderRepository:
    """Pengingat pada agenda, beserta orang-orang yang ditandai."""

    @staticmethod
    def _terlihat_oleh(user_id: int):
        """
        Syarat sebuah pengingat terlihat oleh seseorang.

        Tiga jalan, dan cukup salah satunya:
          - ia pembuatnya;
          - pengingat ditujukan untuk seluruh pengguna;
          - namanya ada pada daftar yang ditandai.

        Ditulis sebagai satu fungsi karena dipakai pada beberapa kueri;
        menyalinnya berarti suatu saat salah satunya diperbarui sendirian.
        """
        ditandai = select(reminder_targets_table.c.reminderID).where(
            reminder_targets_table.c.userID == user_id
        )
        return or_(
            reminders_table.c.createdBy == user_id,
            reminders_table.c.isShared == True,  # noqa: E712
            reminders_table.c.id.in_(ditandai),
        )

    @staticmethod
    async def get_range(user_id: int, dari: d, sampai: d):
        """Pengingat yang terlihat oleh seseorang dalam rentang tanggal."""
        try:
            query = (
                select(
                    reminders_table,
                    users_table.c.name.label("createdByName"),
                )
                .select_from(
                    reminders_table.outerjoin(
                        users_table, reminders_table.c.createdBy == users_table.c.id
                    )
                )
                .where(
                    reminders_table.c.isDelete == False,  # noqa: E712
                    reminders_table.c.date >= dari,
                    reminders_table.c.date <= sampai,
                    ReminderRepository._terlihat_oleh(user_id),
                )
                .order_by(reminders_table.c.date.asc(), reminders_table.c.id.asc())
            )
            baris = await database.fetch_all(query)
            hasil = [dict(b) for b in baris]

            if not hasil:
                return hasil

            # Orang yang ditandai diambil sekaligus, bukan per pengingat:
            # satu kueri untuk seluruh daftar, bukan satu kueri per baris.
            ids = [r["id"] for r in hasil]
            tandaan = await database.fetch_all(
                select(
                    reminder_targets_table.c.reminderID,
                    reminder_targets_table.c.userID,
                    users_table.c.name,
                )
                .select_from(
                    reminder_targets_table.join(
                        users_table,
                        reminder_targets_table.c.userID == users_table.c.id,
                    )
                )
                .where(reminder_targets_table.c.reminderID.in_(ids))
            )

            per_pengingat: dict[int, list] = {}
            for t in tandaan:
                per_pengingat.setdefault(t["reminderID"], []).append(
                    {"id": t["userID"], "name": t["name"]}
                )

            for r in hasil:
                r["targets"] = per_pengingat.get(r["id"], [])
            return hasil
        except Exception as e:
            log_error(f"Error fetching reminders: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_by_id(reminder_id: int):
        try:
            baris = await database.fetch_one(
                select(reminders_table).where(reminders_table.c.id == reminder_id)
            )
            return dict(baris) if baris else None
        except Exception as e:
            log_error(f"Error fetching reminder {reminder_id}: {str(e)}")
            return internal_error()

    @staticmethod
    async def create(data: dict, target_ids: List[int]):
        try:
            reminder_id = await database.execute(insert(reminders_table).values(**data))
            await ReminderRepository._set_targets(reminder_id, target_ids)
            return {"id": reminder_id}
        except Exception as e:
            log_error(f"Error creating reminder: {str(e)}")
            return internal_error()

    @staticmethod
    async def update(reminder_id: int, data: dict, target_ids: List[int] | None):
        try:
            if data:
                await database.execute(
                    update(reminders_table)
                    .where(reminders_table.c.id == reminder_id)
                    .values(**data)
                )
            # `None` berarti daftar tandaan tidak ikut diubah; daftar kosong
            # berarti seluruh tandaan dilepas.
            if target_ids is not None:
                await ReminderRepository._set_targets(reminder_id, target_ids)
            return {"message": "Reminder updated successfully"}
        except Exception as e:
            log_error(f"Error updating reminder {reminder_id}: {str(e)}")
            return internal_error()

    @staticmethod
    async def soft_delete(reminder_id: int):
        try:
            await database.execute(
                update(reminders_table)
                .where(reminders_table.c.id == reminder_id)
                .values(isDelete=True)
            )
            return {"message": "Reminder deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting reminder {reminder_id}: {str(e)}")
            return internal_error()

    @staticmethod
    async def _set_targets(reminder_id: int, target_ids: List[int]):
        """Ganti seluruh daftar tandaan; yang lama dibuang."""
        await database.execute(
            delete(reminder_targets_table).where(
                reminder_targets_table.c.reminderID == reminder_id
            )
        )
        for uid in dict.fromkeys(target_ids or []):
            await database.execute(
                insert(reminder_targets_table).values(
                    reminderID=reminder_id, userID=uid
                )
            )


class TaggableUserRepository:
    """
    Orang yang dapat ditandai pada sebuah pengingat.

    Endpoint tersendiri, tidak memakai daftar pengguna biasa, karena dua
    alasan:

      * daftar pengguna dijaga `user:read` yang berada di akses 5 — staf
        tidak akan melihat satu nama pun, dan penandaannya menjadi fitur
        yang hanya berfungsi bagi pemilik usaha;

      * yang dikembalikan cukup id dan nama. Daftar pengguna memuat surel,
        level, dan status keaktifan, yang tidak diperlukan untuk memilih
        siapa yang ditandai.

    Peminta dikecualikan di sini, bukan di layar: server selalu tahu siapa
    yang meminta, sedangkan layar bergantung pada data yang tersimpan di
    peramban — dan data itu bisa tertinggal dari sesi sebelumnya.
    """

    @staticmethod
    async def list_for(user_id: int):
        try:
            baris = await database.fetch_all(
                select(users_table.c.id, users_table.c.name)
                .where(
                    users_table.c.id != user_id,
                    users_table.c.isDeleted == False,  # noqa: E712
                )
                .order_by(users_table.c.name.asc())
            )
            return [{"id": b["id"], "name": b["name"]} for b in baris]
        except Exception as e:
            log_error(f"Error fetching taggable users: {str(e)}")
            return internal_error()


class BirthdayRepository:
    """
    Ulang tahun karyawan aktif.

    Sengaja terpisah dari repository karyawan, dan hanya mengembalikan nama
    beserta tanggal-bulannya.

    Tahun lahir tidak ikut: tanggal lahir lengkap dipakai di banyak tempat
    untuk memastikan identitas seseorang, dan mengumumkan usia seluruh
    karyawan bukan hal yang setiap orang nyaman. Untuk mengucapkan selamat,
    tanggal dan bulan sudah cukup.
    """

    @staticmethod
    async def upcoming(hari_ini: d, jangkauan: int = 7):
        try:
            baris = await database.fetch_all(
                select(
                    employees_table.c.id,
                    employees_table.c.name,
                    employees_table.c.birthday,
                ).where(
                    employees_table.c.isDelete == False,  # noqa: E712
                    employees_table.c.birthday.isnot(None),
                    # Hanya karyawan yang masih bekerja.
                    #
                    # `endDate` adalah TANGGAL TERAKHIR BEKERJA: terisi
                    # berarti orangnya sudah tidak aktif. Itulah penanda
                    # statusnya — tidak ada kolom status tersendiri.
                    #
                    # Mengingatkan ulang tahun orang yang sudah keluar bukan
                    # sekadar sia-sia: namanya muncul di agenda seluruh
                    # kantor dan mengundang ucapan yang canggung.
                    employees_table.c.endDate.is_(None),
                )
            )

            hasil = []
            for b in baris:
                lahir = b["birthday"]
                if not lahir:
                    continue
                selisih = BirthdayRepository.days_until(
                    lahir.month, lahir.day, hari_ini
                )
                if selisih is None or selisih > jangkauan:
                    continue
                hasil.append(
                    {
                        "id": b["id"],
                        "name": b["name"],
                        "day": lahir.day,
                        "month": lahir.month,
                        "daysUntil": selisih,
                    }
                )

            hasil.sort(key=lambda x: (x["daysUntil"], x["name"]))
            return hasil
        except Exception as e:
            log_error(f"Error fetching birthdays: {str(e)}")
            return internal_error()

    @staticmethod
    async def in_range(dari: d, sampai: d):
        """
        Ulang tahun yang jatuh di dalam rentang tanggal.

        Berbeda dari `upcoming` yang hanya melihat ke DEPAN dari hari ini,
        fungsi ini menerima rentang bebas — termasuk yang seluruhnya sudah
        lewat. Tampilan kalender bulanan perlu itu: membuka bulan lalu tidak
        boleh menghasilkan halaman kosong.

        Pencocokannya per hari, bukan lewat kueri, karena yang dibandingkan
        adalah bulan dan tanggal tanpa memandang tahun — dan rentangnya
        selalu pendek (paling banyak beberapa pekan), sehingga menelusuri
        harinya jauh lebih sederhana daripada menyusun kondisi SQL yang
        menangani pergantian tahun.
        """
        try:
            baris = await database.fetch_all(
                select(
                    employees_table.c.id,
                    employees_table.c.name,
                    employees_table.c.birthday,
                ).where(
                    employees_table.c.isDelete == False,  # noqa: E712
                    employees_table.c.birthday.isnot(None),
                    # Hanya karyawan yang masih bekerja.
                    #
                    # `endDate` adalah TANGGAL TERAKHIR BEKERJA: terisi
                    # berarti orangnya sudah tidak aktif. Itulah penanda
                    # statusnya — tidak ada kolom status tersendiri.
                    #
                    # Mengingatkan ulang tahun orang yang sudah keluar bukan
                    # sekadar sia-sia: namanya muncul di agenda seluruh
                    # kantor dan mengundang ucapan yang canggung.
                    employees_table.c.endDate.is_(None),
                )
            )

            # (bulan, tanggal) -> tanggal sebenarnya dalam rentang
            peta: dict[tuple[int, int], d] = {}
            kursor = dari
            while kursor <= sampai:
                peta.setdefault((kursor.month, kursor.day), kursor)
                kursor = kursor + timedelta(days=1)

            hasil = []
            for b in baris:
                lahir = b["birthday"]
                if not lahir:
                    continue
                kunci = (lahir.month, lahir.day)
                # 29 Februari pada tahun biasa diperlakukan sebagai 1 Maret,
                # sama seperti pada `days_until`.
                if kunci == (2, 29) and kunci not in peta:
                    kunci = (3, 1)
                if kunci not in peta:
                    continue
                tanggal = peta[kunci]
                hasil.append(
                    {
                        "id": b["id"],
                        "name": b["name"],
                        "birthday": lahir,
                        "date": tanggal,
                        "age": tanggal.year - lahir.year,
                    }
                )
            hasil.sort(key=lambda x: (x["date"], x["name"]))
            return hasil
        except Exception as e:
            log_error(f"Error fetching birthdays in range: {str(e)}")
            return internal_error()

    @staticmethod
    def days_until(bulan: int, hari: int, hari_ini: d) -> int | None:
        """
        Berapa hari lagi menuju tanggal tersebut, tanpa memandang tahun.

        Perbandingannya tidak boleh memakai tahun lahir: pada 28 Desember,
        ulang tahun 3 Januari harus terhitung 6 hari lagi — bukan terlewat
        360 hari.

        29 Februari pada tahun biasa dihitung sebagai 1 Maret, agar orangnya
        tetap muncul setiap tahun.
        """
        def _buat(tahun: int):
            try:
                return d(tahun, bulan, hari)
            except ValueError:
                if bulan == 2 and hari == 29:
                    return d(tahun, 3, 1)
                return None

        berikut = _buat(hari_ini.year)
        if berikut is None:
            return None
        if berikut < hari_ini:
            berikut = _buat(hari_ini.year + 1)
            if berikut is None:
                return None
        return (berikut - hari_ini).days
