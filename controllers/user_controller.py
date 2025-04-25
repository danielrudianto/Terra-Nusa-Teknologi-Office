from sqlalchemy import insert, select
from utils.database import database
from models.user_model import users_table
from utils.error_handler import handle_error
from bcrypt import hashpw, gensalt, checkpw
from fastapi.responses import JSONResponse
from services.user_service import UserService

class UserController:
    @staticmethod
    async def create_user(user_data: dict):
        try:
            query = insert(user_data).values(**user_data)
            user_id = await database.execute(query)
            return {"message": "User created successfully", "user_id": user_id}
        except Exception as e:
            handle_error(400, str(e))
            
    @staticmethod
    async def login(user_data: dict):
        try:
            result = await UserService.get_user_by_email(user_data["email"])

            # Check if the user exists
            if result is None:
                raise ValueError("Email and password does not match")

            # Verify the password
            if checkpw(user_data["password"].encode("utf-8"), result.password.encode("utf-8")):
                return JSONResponse({
                    "message": "Login successful",
                    "user_id": result.id,
                    "email": result.email,
                })
            else:
                raise ValueError("Email and password does not match")
        except Exception as e:
            # Catch any unexpected errors and return them
            raise Exception(e)
            
    @staticmethod
    async def register(user_data: dict):
        try:
            hashed_password = hashpw(user_data["password"].encode("utf-8"), gensalt())
            user_data["password"] = hashed_password.decode("utf-8")
            query = insert(users_table).values(**user_data)
            user_id = await database.execute(query)
            return {"message": "User registered successfully", "user_id": user_id}
        except Exception as e:
            handle_error(400, str(e))