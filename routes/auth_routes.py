from fastapi import APIRouter, HTTPException, Request
from models.auth_model import LoginData
from controllers.user_controller import UserController
from datetime import datetime, timedelta, timezone
from utils.logger_utils import log_error, log_info
import jwt
from utils.auth_utils import (
    ALGORITHM,
    SECRET_KEY,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    validate_token,
)
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
        # Nama ikut sejak awal: refresh token adalah sumber isi seluruh
        # access token berikutnya, dan jejak aktivitas mengambil nama pelaku
        # dari sana.
        "name": result["name"],
        "exp": int((now + timedelta(days=7)).timestamp()),  # Refresh token expires in 30 days
        "iat": int(now.timestamp())
    }

    user = {
        # Id ikut dikirim karena layar memakainya untuk mengenali "saya":
        # menyembunyikan tombol setujui pada dokumen buatan sendiri, dan
        # menyaring diri sendiri dari daftar orang yang dapat ditandai.
        #
        # Tanpa id, keduanya diam-diam tidak berfungsi — tidak ada galat,
        # hanya penjagaan yang tidak pernah menyala.
        "id": result["id"],
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
    """
    Perbarui access token, sekaligus menerbitkan refresh token baru.

    Sebelumnya hanya access token yang dikembalikan, sehingga refresh token
    tidak pernah diperbarui: yang dipegang pengguna tetap milik login
    pertamanya, dan masa berlakunya terus berjalan. Setelah 7 hari, ia
    kedaluwarsa dan penyegaran gagal — meski orang tersebut memakai aplikasi
    setiap hari.

    Gejalanya menyesatkan: pengguna yang jarang menutup aplikasi justru yang
    lebih dulu terlempar, sementara yang rutin masuk-keluar tidak pernah
    mengalaminya karena selalu mendapat token baru dari proses login.
    """
    header = request.headers.get("x-refresh-token") or ""
    bagian = header.split(" ")
    refresh_token = bagian[1] if len(bagian) > 1 else ""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not provided")

    # Decode the refresh token
    token_data = validate_token(refresh_token)
    if isinstance(token_data, dict) and "error" in token_data:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
    # Nama ikut dibawa ke refresh token yang baru.
    #
    # Refresh token adalah sumber isi seluruh access token berikutnya; bila
    # namanya berhenti di sini, seluruh penyegaran setelahnya menghasilkan
    # token tanpa nama, dan jejak aktivitas kehilangan pelakunya.
    isi_refresh = {
        "user_id": payload.get("user_id"),
        "iat": datetime.now(timezone.utc),
    }
    if payload.get("name"):
        isi_refresh["name"] = payload["name"]

    new_refresh = create_access_token(
        isi_refresh,
        timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": token_data,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }