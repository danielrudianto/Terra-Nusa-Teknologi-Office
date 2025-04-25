from fastapi import APIRouter
from controllers.user_controller import UserController
from models.user_model import User
from utils.error_handler import handle_error

router = APIRouter()

@router.post("/")
async def create_user(user: User):
    result = await UserController.create_user(user.dict())
    if "error" in result:
        handle_error(400, result["error"])
    return result