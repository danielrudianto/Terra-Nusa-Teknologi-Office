from fastapi import APIRouter, HTTPException
from models.auth_model import LoginData
from controllers.user_controller import UserController
from datetime import datetime, timedelta
from pyseto import Paseto
from utils.auth_utils import KEY
from utils.logger_utils import log_error, log_info

router = APIRouter()

@router.post("/")
async def login(loginData: LoginData):
    try:
        # Attempt to log in the user
        result = await UserController.login(loginData.model_dump())
        
        # Check for errors in the result
        if "error" in result:
            log_error("Login failed for user %s: %s", loginData.username, result["error"])
            raise HTTPException(status_code=400, detail=result["error"])
        
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
        # Handle specific value errors
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal server error.")
    
