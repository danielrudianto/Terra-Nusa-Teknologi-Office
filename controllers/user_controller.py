from repository.user_repository import UserRepository
from schemas.user_schema import UserCreate, UserLogin, LoginResponse, ErrorResponse
from utils.logger_utils import log_error, log_info
from fastapi import HTTPException
import bcrypt

class UserController:
    @staticmethod
    async def create_user(user_data: dict):
        try:
            result = await UserRepository.create_user(user_data)
            return result
        except Exception as e:
            log_error("Error creating user: %s", str(e))
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def login(login_data: dict):
        try:
            user = await UserRepository.get_user_by_email(login_data['email'])
            
            if user is None:
                log_info("Login failed - invalid credentials")
                return ErrorResponse(
                    error="Email or password is incorrect", 
                    status=401
                )
                
            #Check the password
            checkpass = bcrypt.checkpw(login_data["password"].encode("utf-8"), user["password"].encode("utf-8"))

            log_info(f"Login successful for user ID: {user.id}")
            return user
            
        except Exception as e:
            log_error(f"Login error: {str(e)}")
            return ErrorResponse(error="Internal server error", status=500)