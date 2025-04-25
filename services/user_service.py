from sqlalchemy import insert, select
from utils.database import database
from models.user_model import users_table
from bcrypt import hashpw, gensalt
from pymysql.err import ProgrammingError
from utils.logger_utils import log_error

class UserService:
    @staticmethod
    async def create_user(user_data: dict):
        hashed_password = hashpw(user_data["password"].encode("utf-8"), gensalt())
        user_data["password"] = hashed_password.decode("utf-8")
        query = insert(users_table).values(**user_data)
        try:
            user_id = await database.execute(query)
            return user_id
        except Exception as e:
            # Handle specific exceptions if needed
            raise e

    @staticmethod
    async def get_user_by_email(email: str):
        query = select(users_table).where(users_table.c.email == email)
        try:
            result = await database.fetch_one(query)
            return result
        except ProgrammingError as e:
            log_error(str(e))
            raise ProgrammingError("Database error")
        except Exception as e:
            log_error(str(e))
            raise Exception(str(e))

    @staticmethod
    async def register(user_data: dict):
        return await UserService.create_user(user_data)