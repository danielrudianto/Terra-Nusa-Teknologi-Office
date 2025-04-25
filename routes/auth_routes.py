from fastapi import APIRouter
from models.auth_model import LoginData
from controllers.user_controller import UserController
from utils.error_handler import handle_error
from datetime import datetime, timedelta
from pyseto import Paseto
from utils.auth_utils import KEY
from utils.logger_utils import log_request
from fastapi.responses import JSONResponse

router = APIRouter()

@router.post("/")
async def login(loginData: LoginData):
    try:
        result = await UserController.login(loginData.model_dump())
        if "error" in result:
            handle_error(400, result["error"])
        #Generate JWT token
        # Generate JWT token
        payload = {
            "user_id": result["user_id"],
            "name": result["name"],
            "exp": (datetime.utcnow() + timedelta(hours=1)).isoformat(),  # Token expires in 1 hour
            "iat": datetime.utcnow().isoformat(),  # Issued at
        }
        token = Paseto.new(version=4, purpose="local").encrypt(KEY, payload)
        
        return {"access_token": token, "token_type": "bearer"}
    except ValueError as e:
        print(e)
    except Exception as e:
        return JSONResponse(
            {
                "messsage": "Whoops, something is wrong on our side. Please contact your administrator"
            },
            status_code=500
        )
    
