from sqlalchemy import insert, select, update, func, or_
import bcrypt
from utils.database import database
from models.user_model import users_table
from datetime import datetime




def _hash_sandi(nilai) -> str:
    """
    Ubah sandi menjadi hash bcrypt.

    Dipasang di REPOSITORY, bukan di controller: `create_user` meneruskan
    muatannya apa adanya ke `values(**user_data)`, sehingga sandi tersimpan
    telanjang di basis data — terbaca oleh siapa pun yang dapat membuka
    tabelnya, termasuk dari cadangan yang bocor.

    Yang sudah berupa hash TIDAK di-hash ulang. Tanpa penjagaan itu,
    pemanggil yang sudah melakukannya sendiri — `update_user` dan
    `change_own_password` — akan menghasilkan hash berlapis, dan sandi yang
    benar pun ditolak saat masuk.
    """
    teks = str(nilai or "")
    if not teks:
        return teks
    # Hash bcrypt selalu diawali penanda versinya.
    if teks.startswith(("$2a$", "$2b$", "$2y$")):
        return teks
    return bcrypt.hashpw(teks.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _tanpa_sandi(baris):
    """
    Buang kolom sandi sebelum data pengguna meninggalkan server.

    Yang tersimpan memang hash bcrypt, bukan sandi terbaca — tetapi hash itu
    tetap tidak boleh keluar. Ia dapat diserang secara luring tanpa batas
    percobaan, dan sekali bocor tidak ada cara menariknya kembali.

    Dibuang di SINI, bukan di tiap rute: ini satu-satunya pintu yang dilewati
    seluruh pembacaan pengguna, sehingga tidak ada rute yang dapat lupa.
    """
    if baris is None:
        return None
    d = dict(baris)
    d.pop("password", None)
    return d


class UserRepository:
    @staticmethod
    async def create_user(user_data: dict):
        # Model memakai default=datetime.now() yang dievaluasi sekali saat
        # modul di-import, sehingga semua user akan tercatat dengan waktu
        # yang sama. Diisi eksplisit di sini agar benar-benar waktu simpan.
        user_data.setdefault("createdAt", datetime.now())

        # `isActive` dan `isDeleted` juga diisi eksplisit, dengan alasan yang
        # sama seperti `createdAt` di atas.
        #
        # `default=` pada model dievaluasi mesin SQLAlchemy saat eksekusi;
        # pustaka `databases` menjalankan kueri yang sudah dikompilasi,
        # sehingga langkah itu dilewati dan nilainya tersimpan sebagai NULL.
        #
        # Kolomnya nullable, jadi penyimpanannya BERHASIL — dan barulah
        # jawaban rutenya ditolak `response_model` karena NULL bukan boolean.
        # Penggunanya sudah terbuat, tetapi layar menerima galat 500 dan
        # menyangka pembuatannya gagal, lalu mencoba lagi.
        user_data.setdefault("isActive", True)
        user_data.setdefault("isDeleted", False)

        # Sandi DI-HASH sebelum disimpan.
        if user_data.get("password"):
            user_data["password"] = _hash_sandi(user_data["password"])

        query = insert(users_table).values(**user_data)
        user_id = await database.execute(query)

        from repository.audit_log_repository import AuditLogRepository

        # Pada pembuatan tidak ada keadaan sebelumnya untuk dibandingkan;
        # yang dicatat cukup nilai awalnya, tanpa kata sandi.
        awal = {k: v for k, v in user_data.items() if k != "password"}
        await AuditLogRepository.record(
            entity="users",
            entityID=user_id,
            action="create",
            changes=awal or None,
        )

        # Dikembalikan sebagai baris utuh, bukan sekadar id: rutenya memakai
        # UserResponse sebagai response_model, dan angka tidak dapat
        # dipetakan ke sana.
        dibuat = await database.fetch_one(
            select(users_table).where(users_table.c.id == user_id)
        )
        return _tanpa_sandi(dibuat) if dibuat else {"id": user_id}

    @staticmethod
    async def get_user_by_email(email: str):
        query = select(users_table).where(users_table.c.email == email)
        result = await database.fetch_one(query)
        return result

    @staticmethod
    async def get_user_by_id(user_id: int):
        query = select(users_table).where(users_table.c.id == user_id)
        result = await database.fetch_one(query)
        return _tanpa_sandi(result)

    @staticmethod
    async def get_users(keyword: str = None, page: int = 1, pageSize: int = 10, sortBy: str = None, sortByDirection: str = "asc"):
        """Paginated list of non-deleted users with optional keyword search."""
        offset = (page - 1) * pageSize

        base_where = users_table.c.isDeleted == False
        data_query = select(users_table).where(base_where)
        count_query = select(func.count(users_table.c.id)).where(base_where)

        if keyword:
            kw = f"%{keyword}%"
            cond = or_(
                users_table.c.name.ilike(kw),
                users_table.c.email.ilike(kw),
            )
            data_query = data_query.where(cond)
            count_query = count_query.where(cond)

        # Kolom yang boleh dipakai mengurutkan; daftar putih mencegah nama

        # kolom sembarang ikut masuk ke query.

        SORTABLE = {

            "name": users_table.c.name,

            "email": users_table.c.email,

        }

        _kolom = SORTABLE.get(sortBy, users_table.c.name)

        _urut = (

            _kolom.desc()

            if str(sortByDirection).lower() == "desc"

            else _kolom.asc()

        )


        data_query = (
            data_query.order_by(_urut)
            .offset(offset)
            .limit(pageSize)
        )

        rows = await database.fetch_all(data_query)
        total_count = await database.fetch_val(count_query)
        return {
                "data": [_tanpa_sandi(r) for r in rows],
                "count": total_count or 0,
            }

    @staticmethod
    async def update_user(user_id: int, values: dict):
        # Sandi DI-HASH di sini juga, bukan hanya di controller.
        #
        # `_hash_sandi` melewati nilai yang sudah berupa hash, sehingga
        # pemanggil yang sudah melakukannya sendiri tidak menghasilkan hash
        # berlapis. Yang dijaga adalah jalur yang LUPA melakukannya.
        if values.get("password"):
            values["password"] = _hash_sandi(values["password"])

        # Keadaan sebelum dibaca lebih dulu; setelah update nilai lamanya
        # sudah tertimpa dan tidak bisa direkam lagi.
        _sebelum = await database.fetch_one(
            select(users_table).where(users_table.c.id == user_id)
        )
        query = (
            update(users_table)
            .where(users_table.c.id == user_id)
            .values(**values, updatedAt=datetime.now())
        )
        await database.execute(query)
        from repository.audit_log_repository import AuditLogRepository

        await AuditLogRepository.record(
            entity="users",
            changes=AuditLogRepository.diff(
                dict(_sebelum) if _sebelum else {}, values
            ),
            entityID=user_id,
            action="update",
        )

        return {"message": "User updated successfully", "user_id": user_id}

    @staticmethod
    async def soft_delete(user_id: int):
        # Keadaan sebelum dibaca lebih dulu; setelah ditandai terhapus,
        # nilai lamanya tidak bisa direkam lagi.
        _sebelum = await database.fetch_one(
            select(users_table).where(users_table.c.id == user_id)
        )
        nilai = {"isDeleted": True, "deletedAt": datetime.now()}
        query = (
            update(users_table).where(users_table.c.id == user_id).values(**nilai)
        )
        await database.execute(query)
        from repository.audit_log_repository import AuditLogRepository

        await AuditLogRepository.record(
            entity="users",
            changes=AuditLogRepository.diff(
                dict(_sebelum) if _sebelum else {}, nilai
            ),
            entityID=user_id,
            action="delete",
        )

        return {"message": "User deleted successfully"}
