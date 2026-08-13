from fastapi import HTTPException, Depends
from utils.logger_utils import log_error, log_info
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta, timezone
import jwt
import os
from typing import Annotated
from jwt.exceptions import InvalidTokenError

from pydantic import BaseModel
from passlib.context import CryptContext
from models.user_model import users_table
from utils.database import database

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
# Masa berlaku token, dapat diatur lewat variabel lingkungan.
#
# Sebelumnya access token hanya 1 menit sementara pemanggilan dari halaman
# login memakai 12 jam — dua angka berbeda untuk hal yang sama. Nilai di sini
# dijadikan satu-satunya acuan.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Refresh token harus LEBIH PANJANG dari access token; kalau lebih pendek,
# pengguna tetap terlempar keluar meski access token-nya masih berlaku.
REFRESH_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7))
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None

class UserInDB(User):
    hashed_password: str

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(username: str, password: str):
    """
    TIDAK DIPAKAI — jangan dipanggil sebelum diperbaiki.

    Sisa dari kerangka awal: memakai kolom `username` dan `hashed_password`
    yang tidak ada pada tabel users (kolomnya `email` dan `password`), serta
    `.first()` yang bukan cara pustaka ini membaca baris.

    Autentikasi yang sebenarnya ada di `routes/auth_routes.py`. Fungsi ini
    dibiarkan agar tidak menghapus sesuatu yang mungkin dirujuk dari luar,
    tetapi memanggilnya akan gagal.
    """
    user = users_table.select().where(users_table.c.username == username).first()    
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def validate_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        userID = payload.get("user_id")
        if userID is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials 1")

        # Nama ikut dibawa ke token baru.
        #
        # Jejak aktivitas mengambil nama pelaku dari token, tanpa kueri
        # tambahan. Bila nama tidak ikut, seluruh catatan yang dibuat setelah
        # penyegaran pertama kehilangan pelakunya — dan itu tidak terlihat
        # sebagai galat, hanya sebagai kolom yang berisi tanda hubung.
        data = {"user_id": userID, "iat": datetime.now(timezone.utc)}
        nama = payload.get("name") or payload.get("sub")
        if nama:
            data["name"] = nama

        token_data = create_access_token(data=data)
        return token_data
    except InvalidTokenError:
        return {"error": "Invalid authentication credentials", "status": 401}

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        userID = payload.get("user_id")
        if userID is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials 1")
    
        query = users_table.select().where(users_table.c.id == userID)
        user = await database.fetch_one(query)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials 2")
        return user
    except InvalidTokenError as e:
        print(e)
        raise HTTPException(status_code=401, detail="Invalid authentication credentials 3")
    except Exception as e:
        print(e)


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire.timestamp()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt