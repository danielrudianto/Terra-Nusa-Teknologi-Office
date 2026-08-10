from fastapi import APIRouter, HTTPException, Request
from models.auth_model import LoginData
from controllers.user_controller import UserController
from datetime import datetime, timedelta
from utils.logger_utils import log_error, log_info
from utils.auth_utils import create_access_token, validate_token, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_MINUTES
from utils.login_guard import cek_terkunci, catat_gagal, bersihkan
from utils.auth_utils import User

router = APIRouter()

@router.post("/")
async def login(loginData: LoginData, request: Request):
    ip = request.client.host if request.client else None

    # Diperiksa sebelum kata sandi dicocokkan, supaya percobaan yang sudah
    # melewati batas tidak ikut membebani proses hashing.
    sisa = cek_terkunci(loginData.email, ip)
    if sisa:
        log_error(f"Login diblokir sementara untuk {loginData.email}")
        raise HTTPException(
            status_code=429,
            detail=(
                "Terlalu banyak percobaan masuk. "
                f"Coba lagi dalam {max(1, sisa // 60)} menit."
            ),
        )

    result = await UserController.login(loginData.model_dump())

    # Check for errors in the result
    if "error" in result:
        catat_gagal(loginData.email, ip)
        log_error(f"Login failed for user {loginData.email}")
        # Pesan sengaja tidak membedakan email salah dan kata sandi salah,
        # agar tidak bisa dipakai menebak email mana yang terdaftar.
        raise HTTPException(status_code=400, detail="Invalid credentials")

    bersihkan(loginData.email, ip)
    
    now = datetime.utcnow()

    # Generate JWT token
    payload = {
        "user_id": result["id"],
        "name": result["name"],
        "exp": int(
            (now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()
        ),
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

    # Masa berlaku diambil dari satu tempat agar tidak berbeda antar
    # pemanggilan; refresh selalu lebih panjang dari access.
    token = create_access_token(
        payload, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_access_token(
        refresh_payload, timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    )
    
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