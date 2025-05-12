from sqlalchemy import insert, select
from utils.database import database
from models.user_model import users_table
from bcrypt import hashpw, gensalt, checkpw
from fastapi.responses import JSONResponse
from services.user_service import UserService
from utils.logger_utils import log_error, log_info
from fastapi import HTTPException

class UserController:
    @staticmethod
    async def create_user(user_data: dict):
        try:
            query = insert(user_data).values(**user_data)
            user_id = await database.execute(query)
            return {"message": "User created successfully", "user_id": user_id}
        except Exception as e:
            log_error("Error creating user: %s", str(e))
            raise e
            
    @staticmethod
    async def login(user_data: dict):
        try:
            result = await UserService.get_user_by_email(user_data["email"])

            # Check if the user exists
            if result is None:
                log_info("User not found")
                return {"error": "Email or password is incorrect", "status": 401}

            # Verify the password
            if checkpw(user_data["password"].encode("utf-8"), result.password.encode("utf-8")):
                log_info(f"Password verified for user ID: {result.id}")
                return {
                    "message": "Login successful",
                    "user_id": result.id,
                    "email": result.email,
                    "name": result.name,
                }
            else:
                #print hashed password
                log_info("Password verification failed")
                return {"error": "Email or password is incorrect", "status": 401}
        except Exception as e:
            log_error(e)
            return {"error": "Internal server error", "status": 500}
            
    @staticmethod
    async def register(user_data: dict):
        try:
            hashed_password = hashpw(user_data["password"].encode("utf-8"), gensalt())
            user_data["password"] = hashed_password.decode("utf-8")
            query = insert(users_table).values(**user_data)
            user_id = await database.execute(query)
            return {"message": "User registered successfully", "user_id": user_id}
        except Exception as e:
            log_error("Error registering user: %s", str(e))
            raise e