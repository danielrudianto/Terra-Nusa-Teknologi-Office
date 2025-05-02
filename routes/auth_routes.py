from fastapi import APIRouter, HTTPException
from models.auth_model import LoginData
from controllers.user_controller import UserController
from datetime import datetime, timedelta
from utils.auth_utils import KEY
from utils.logger_utils import log_error, log_info
from pyseto import Key
import pyseto
import json

router = APIRouter()

@router.post("/")
async def login(loginData: LoginData):
    try:
        # Attempt to log in the user
        result = await UserController.login(loginData.model_dump())
        
        # Check for errors in the result
        if "error" in result:
            log_info(f"Login failed for user {loginData.email}")
            raise HTTPException(status_code=result.status, detail=result["error"])
        
        # Generate JWT token
        payload = {
            "user_id": result["user_id"],
            "name": result["name"],
            "exp": (datetime.utcnow() + timedelta(hours=1)).isoformat(),  # Token expires in 1 hour
            "iat": datetime.utcnow().isoformat(),  # Issued at
        }

        refresh_payload = {
            "user_id": result["user_id"],
            "exp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),  # Refresh token expires in 30 days
            "iat": datetime.utcnow().isoformat(),  # Issued at
        }
        
        token = pyseto.encode(KEY, payload, serializer=json)
        refresh_token = pyseto.encode(KEY, refresh_payload, serializer=json)
        
        return {"access_token": token, "refresh_token": refresh_token, "token_type": "bearer"}
    except Exception as e:
        log_error(f"Error during login: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
