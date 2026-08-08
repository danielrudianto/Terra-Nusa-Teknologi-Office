from repository.user_repository import UserRepository
from schemas.user_schema import UserCreate, UserLogin, LoginResponse, ErrorResponse
from utils.logger_utils import log_error, log_info
from fastapi import HTTPException
import bcrypt


def _strip_password(user: dict) -> dict:
    """Never expose the password hash to the client."""
    if user is None:
        return None
    u = dict(user)
    u.pop("password", None)
    return u


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
    async def get_users(keyword: str = None, page: int = 1, pageSize: int = 10):
        try:
            if page < 1:
                return {"error": "Page number must be greater than 0", "status": 400}
            result = await UserRepository.get_users(keyword, page, pageSize)
            # strip password from every row
            result["data"] = [_strip_password(u) for u in result["data"]]
            return result
        except Exception as e:
            log_error(f"Error retrieving users: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_user_by_id(user_id: int):
        try:
            user = await UserRepository.get_user_by_id(user_id)
            if user is None:
                return {"error": "User not found", "status": 404}
            return _strip_password(user)
        except Exception as e:
            log_error(f"Error fetching user: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update_user(user_id: int, user_data: dict):
        try:
            existing = await UserRepository.get_user_by_id(user_id)
            if existing is None:
                return {"error": "User not found", "status": 404}

            values = {
                "name": user_data.get("name"),
                "email": user_data.get("email"),
                "authenticationLevel": user_data.get("authenticationLevel"),
            }
            if "isActive" in user_data and user_data["isActive"] is not None:
                values["isActive"] = user_data["isActive"]

            # password optional: only update when a non-empty value is provided
            new_password = (user_data.get("password") or "").strip()
            if new_password:
                hashed = bcrypt.hashpw(
                    new_password.encode("utf-8"), bcrypt.gensalt()
                )
                values["password"] = hashed.decode("utf-8")

            # drop None values so we don't overwrite with nulls
            values = {k: v for k, v in values.items() if v is not None}

            return await UserRepository.update_user(user_id, values)
        except Exception as e:
            log_error(f"Error updating user: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def delete_user(user_id: int):
        try:
            existing = await UserRepository.get_user_by_id(user_id)
            if existing is None:
                return {"error": "User not found", "status": 404}
            return await UserRepository.soft_delete(user_id)
        except Exception as e:
            log_error(f"Error deleting user: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

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