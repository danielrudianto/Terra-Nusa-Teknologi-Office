from fastapi import APIRouter, HTTPException
from controllers.user_controller import UserController
from schemas.user_schema import UserCreate, UserLogin, UserResponse, LoginResponse, ErrorResponse
from utils.logger_utils import log_error

router = APIRouter()

@router.post("/", response_model=UserResponse)
async def create_user(user: UserCreate):
    result = await UserController.create_user(user.dict())
    if "error" in result:
        log_error(f"Error during creating user: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result