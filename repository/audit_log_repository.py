from sqlalchemy import select, insert, func, desc
from utils.database import database
from utils.logger_utils import log_error
from models.audit_log_model import audit_logs_table
from models.user_model import users_table
from utils.audit_context import (
    get_current_ip,
    get_current_user_id,
    get_current_user_name,
)
from datetime import date as tanggal, datetime as dt


class AuditLogRepository:
    """Pencatatan dan pembacaan jejak audit."""

    # Kolom yang tidak perlu dicatat: nilainya berubah pada tiap penyimpanan
    # dan tidak menjelaskan apa pun bagi pembaca.
    ABAIKAN = {"updatedAt", "createdAt", "updatedBy", "id"}

    # Kolom yang perubahannya dicatat, tetapi NILAINYA tidak.
    #
    # Hash bcrypt bukan sesuatu yang boleh tersimpan di tabel yang dibaca
    # lewat halaman Aktivitas. Yang berguna untuk penelusuran adalah fakta
    # "sandi pernah diganti, oleh siapa, kapan" — bukan hashnya.
    RAHASIA = {"password", "hashed_password", "refresh_token", "access_token"}
    TERSAMAR = "(disembunyikan)"

    @staticmethod
    def diff(sebelum: dict, sesudah: dict) -> dict:
        """
        Bandingkan dua keadaan, kembalikan hanya kolom yang benar-benar berubah.

        Menyimpan seluruh isi baris membuat tabel audit membengkak dan justru
        menyulitkan pembacaan; yang dicari orang adalah "apa yang berubah".
        """
        hasil = {}
        for kolom, baru in (sesudah or {}).items():
            if kolom in AuditLogRepository.ABAIKAN:
                continue
            lama = (sebelum or {}).get(kolom)
            if lama == baru:
                continue
            if kolom in AuditLogRepository.RAHASIA:
                hasil[kolom] = {
                    "from": AuditLogRepository.TERSAMAR,
                    "to": AuditLogRepository.TERSAMAR,
                }
                continue
            hasil[kolom] = {
                "from": AuditLogRepository._sederhanakan(lama),
                "to": AuditLogRepository._sederhanakan(baru),
            }
        return hasil

    @staticmethod
    def _sederhanakan(nilai):
        """
        Ubah nilai yang tidak dikenal JSON menjadi bentuk yang dapat disimpan.

        `date` DIPERIKSA, bukan hanya `datetime`.

        Keduanya bukan hal yang sama: `datetime` adalah turunan `date`, tetapi
        TIDAK sebaliknya. Memeriksa `datetime` saja meloloskan `date` apa
        adanya, dan penyandiannya gagal dengan "Object of type date is not
        JSON serializable".

        Kegagalan itu ditelan `record()` — operasi utamanya tetap berhasil,
        hanya jejaknya yang hilang. Sudah terjadi pada `endDate` karyawan:
        yang menonaktifkan karyawan tidak meninggalkan jejak sama sekali di
        halaman Aktivitas, dan tidak ada yang tampak salah dari layar.

        Memeriksa `date` menangkap KEDUANYA, karena `datetime` turunannya.
        """
        if isinstance(nilai, tanggal):
            return nilai.isoformat()
        if hasattr(nilai, "quantize"):  # Decimal
            return float(nilai)
        return nilai

    @staticmethod
    async def record(
        entity: str,
        entityID: int,
        action: str,
        userID: int = None,
        userName: str = None,
        changes: dict = None,
        note: str = None,
        ipAddress: str = None,
    ):
        """
        Catat satu kejadian.

        Kegagalan pencatatan tidak boleh membatalkan operasi utama: lebih baik
        kehilangan satu baris audit daripada menggagalkan penyimpanan purchase
        order yang sudah benar.
        """
        try:
            # Bila pemanggil tidak menyebut penggunanya, ambil dari konteks
            # permintaan — sebagian besar method penulisan tidak menerima
            # user_id pada tanda tangannya.
            if userID is None:
                userID = get_current_user_id()
            if userName is None:
                userName = get_current_user_name()
            if ipAddress is None:
                ipAddress = get_current_ip()

            query = insert(audit_logs_table).values(
                entity=entity,
                entityID=entityID,
                action=action,
                userID=userID,
                userName=userName,
                changes=changes or None,
                note=note,
                ipAddress=ipAddress,
                createdAt=dt.now(),
            )
            await database.execute(query)
            return True
        except Exception as e:
            # Sebab dan ENTITASNYA ikut dicatat.
            #
            # Pesan tanpa entitas membuat penelusuran harus menebak modul mana
            # yang bermasalah — dan "Object of type date is not JSON
            # serializable" muncul sama persis dari lima modul berbeda.
            log_error(
                f"Gagal mencatat jejak audit [{entity}#{entityID} {action}]: "
                f"{str(e)}"
            )
            return False

    @staticmethod
    async def get_by_entity(entity: str, entityID: int, limit: int = 50):
        """Riwayat satu dokumen, terbaru lebih dulu."""
        try:
            # Nama pelaku diambil dari tabel pengguna bila kolom `userName`
            # kosong.
            #
            # Catatan yang dibuat sebelum nama ikut dibawa di dalam token
            # tersimpan tanpa nama, dan tanpa sambungan ini seluruhnya tampil
            # sebagai tanda hubung — padahal `userID`-nya ada, dan namanya
            # masih dapat ditemukan.
            query = (
                select(
                    audit_logs_table,
                    users_table.c.name.label("actorName"),
                )
                .select_from(
                    audit_logs_table.outerjoin(
                        users_table, audit_logs_table.c.userID == users_table.c.id
                    )
                )
                .where(
                    audit_logs_table.c.entity == entity,
                    audit_logs_table.c.entityID == entityID,
                )
                .order_by(desc(audit_logs_table.c.createdAt))
                .limit(limit)
            )
            rows = await database.fetch_all(query)
            data = []
            for r in rows:
                d = dict(r)
                d["userName"] = d.get("userName") or d.pop("actorName", None)
                d.pop("actorName", None)
                data.append(d)
            return {"data": data}
        except Exception as e:
            log_error(f"Error fetching audit log: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_all(
        page: int = 1,
        page_size: int = 25,
        entity: str = None,
        userID: int | list[int] | None = None,
        dateFrom: str = None,
        dateTo: str = None,
    ):
        """Daftar aktivitas seluruh sistem, dengan penyaringan opsional."""
        try:
            conditions = []
            if entity:
                conditions.append(audit_logs_table.c.entity == entity)
            if userID:
                # Satu pengguna atau beberapa sekaligus.
                #
                # Daftar dipakai penyaring di layar, yang membolehkan sampai
                # lima nama. Satu nilai tetap diterima agar pemanggil lama
                # tidak perlu diubah.
                if isinstance(userID, (list, tuple, set)):
                    daftar = [int(x) for x in userID if x is not None]
                    if daftar:
                        conditions.append(audit_logs_table.c.userID.in_(daftar))
                else:
                    conditions.append(audit_logs_table.c.userID == int(userID))
            if dateFrom:
                conditions.append(audit_logs_table.c.createdAt >= dateFrom)
            if dateTo:
                # Batas akhir dibuat inklusif: pengguna memilih tanggal, bukan
                # jam, sehingga kejadian pada hari itu harus ikut terbawa.
                conditions.append(
                    audit_logs_table.c.createdAt < f"{dateTo} 23:59:59.999999"
                )

            # Sama seperti riwayat per dokumen: nama pelaku diambil dari
            # tabel pengguna bila kolom `userName` kosong.
            query = select(
                audit_logs_table,
                users_table.c.name.label("actorName"),
            ).select_from(
                audit_logs_table.outerjoin(
                    users_table, audit_logs_table.c.userID == users_table.c.id
                )
            )
            if conditions:
                query = query.where(*conditions)
            query = (
                query.order_by(desc(audit_logs_table.c.createdAt))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            rows = await database.fetch_all(query)

            count_query = select(func.count()).select_from(audit_logs_table)
            if conditions:
                count_query = count_query.where(*conditions)
            total = await database.fetch_val(count_query)

            data = []
            for r in rows:
                d = dict(r)
                d["userName"] = d.get("userName") or d.pop("actorName", None)
                d.pop("actorName", None)
                data.append(d)

            return {
                "data": data,
                "total": total or 0,
                "page": page,
                "page_size": page_size,
            }
        except Exception as e:
            log_error(f"Error fetching audit logs: {str(e)}")
            return {"error": "Internal server error.", "status": 500}