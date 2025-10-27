from fastapi import APIRouter, HTTPException, Request
from models.auth_model import LoginData
from controllers.user_controller import UserController
from datetime import datetime, timedelta
from utils.logger_utils import log_error, log_info
from utils.auth_utils import create_access_token, validate_token
from utils.auth_utils import User

router = APIRouter()

@router.post("/")
async def login(loginData: LoginData):
    result = await UserController.login(loginData.model_dump())
        
    # Check for errors in the result
    if "error" in result:
        log_error(f"Login failed for user {loginData.email}")
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    now = datetime.utcnow()

    # Generate JWT token
    payload = {
        "user_id": result["id"],
        "name": result["name"],
        "exp": int((now + timedelta(hours=12)).timestamp()),  # Token expires in 1 hour
        "iat": int(now.timestamp()),  # Issued at
    }

    refresh_payload = {
        "user_id": result["id"],
        "exp": int((now + timedelta(days=7)).timestamp()),  # Refresh token expires in 30 days
        "iat": int(now.timestamp())
    }

    user = {
        "name": result["name"],
        "email": result["email"],
        "authenticationLevel": result["authenticationLevel"],
    }

    token = create_access_token(payload, timedelta(hours=12))
    refresh_token = create_access_token(refresh_payload, timedelta(hours=7))
    
    return {"access_token": token, "refresh_token": refresh_token, "token_type": "bearer", "user": user}
    
@router.post("/refresh")
async def refresh_token(request: Request):
    refresh_token = request.headers.get("x-refresh-token").split(" ")[1]
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not provided")
    
    # Decode the refresh token
    token_data = validate_token(refresh_token)
    if "error" in token_data:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    return {"access_token": token_data, "token_type": "bearer"}