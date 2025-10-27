from sqlalchemy import insert, select
from utils.database import database
from models.user_model import users_table

class UserRepository:
    @staticmethod
    async def create_user(user_data: dict):
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