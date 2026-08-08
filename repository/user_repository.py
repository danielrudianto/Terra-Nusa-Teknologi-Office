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
        return user_id

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
    async def get_users(keyword: str = None, page: int = 1, pageSize: int = 10):
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

        data_query = (
            data_query.order_by(users_table.c.name.asc())
            .offset(offset)
            .limit(pageSize)
        )

        rows = await database.fetch_all(data_query)
        total_count = await database.fetch_val(count_query)
        return {"data": [dict(r) for r in rows], "count": total_count or 0}

    @staticmethod
    async def update_user(user_id: int, values: dict):
        query = (
            update(users_table)
            .where(users_table.c.id == user_id)
            .values(**values, updatedAt=datetime.now())
        )
        await database.execute(query)
        return {"message": "User updated successfully", "user_id": user_id}

    @staticmethod
    async def soft_delete(user_id: int):
        query = (
            update(users_table)
            .where(users_table.c.id == user_id)
            .values(isDeleted=True, deletedAt=datetime.now())
        )
        await database.execute(query)
        return {"message": "User deleted successfully"}