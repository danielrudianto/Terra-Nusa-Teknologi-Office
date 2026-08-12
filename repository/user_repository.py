from sqlalchemy import insert, select, update, func, or_
from utils.database import database
from models.user_model import users_table
from datetime import datetime


class UserRepository:
    @staticmethod
    async def create_user(user_data: dict):
        # Model memakai default=datetime.now() yang dievaluasi sekali saat
        # modul di-import, sehingga semua user akan tercatat dengan waktu
        # yang sama. Diisi eksplisit di sini agar benar-benar waktu simpan.
        user_data.setdefault("createdAt", datetime.now())
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
        return dict(dibuat) if dibuat else {"id": user_id}

    @staticmethod
    async def get_user_by_email(email: str):
        query = select(users_table).where(users_table.c.email == email)
        result = await database.fetch_one(query)
        return result

    @staticmethod
    async def get_user_by_id(user_id: int):
        query = select(users_table).where(users_table.c.id == user_id)
        result = await database.fetch_one(query)
        return result

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
        return {"data": [dict(r) for r in rows], "count": total_count or 0}

    @staticmethod
    async def update_user(user_id: int, values: dict):
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
