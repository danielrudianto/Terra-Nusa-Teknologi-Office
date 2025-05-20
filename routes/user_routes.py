from fastapi import APIRouter, HTTPException
from controllers.user_controller import UserController
from models.user_model import User
from utils.logger_utils import log_error

router = APIRouter()

@router.post("/")
async def create_user(user: User):
    result = await UserController.create_user(user.dict())
    if "error" in result:
        log_error(f"Error during creating user: {str(result['error'])}")
        raise HTTPException(status_code=result["status"], detail=result["error"])
    return result