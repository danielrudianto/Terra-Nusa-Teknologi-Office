from fastapi import HTTPException, Depends
from utils.logger_utils import log_error, log_info
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta, timezone
import jwt
import os
from typing import Annotated
from jwt.exceptions import InvalidTokenError

from pydantic import BaseModel
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

# ----------------------------------------------------------------------
# Penanganan sandi TIDAK ada di berkas ini.
# ----------------------------------------------------------------------
#
# Di sini dulu ada `pwd_context` (passlib), `verify_password()`,
# `get_password_hash()`, dan `authenticate_user()` — seluruhnya KODE MATI:
# tidak satu pun dipanggil dari mana pun, dan `authenticate_user` bahkan
# memakai kolom `username`/`hashed_password` yang tidak ada pada tabel users
# (kolomnya `email` dan `password`).
#
# Dibuang, bukan dibiarkan, karena tiga hal:
#
#   1. Namanya MENYESATKAN. `verify_password()` dan `get_password_hash()`
#      terbaca persis seperti jalur sandi yang sebenarnya. Yang menambah
#      fitur dan memanggilnya akan memperoleh hash bcrypt yang sah — lalu
#      menyimpannya lewat jalur yang tidak pernah diuji siapa pun.
#
#   2. `passlib` 1.7.4 mengimpor modul `crypt`, yang SUDAH DIHAPUS pada
#      Python 3.13. Selama paket ini masih terpasang, menaikkan Python akan
#      menjatuhkan seluruh aplikasi pada saat impor — bukan pada satu
#      halaman, melainkan sejak startup. Peringatan usang yang muncul pada
#      setiap deploy adalah pemberitahuan awal atas hal itu.
#
#   3. Ia menarik satu paket utuh hanya untuk kode yang tidak berjalan.
#
# Yang sebenarnya dipakai: `bcrypt` langsung, di `controllers/user_controller.py`
# (`bcrypt.hashpw`, `bcrypt.checkpw`) dan `repository/user_repository.py`.
# Login-nya sendiri di `routes/auth_routes.py`.

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

        # Pengguna yang DINONAKTIFKAN atau DIHAPUS ditolak di sini.
        #
        # Tanpa pemeriksaan ini, menonaktifkan seseorang tidak berpengaruh
        # apa pun sampai tokennya kedaluwarsa — dan masa berlaku refresh
        # token adalah tujuh hari. Orang yang baru saja dikeluarkan tetap
        # dapat menyetujui pembayaran selama seminggu penuh.
        #
        # Diperiksa di sini, bukan pada tiap rute: ini satu-satunya pintu
        # yang dilewati SELURUH permintaan bertoken, sehingga tidak ada rute
        # yang dapat lupa memeriksanya.
        try:
            if not user["isActive"] or user["isDeleted"]:
                raise HTTPException(
                    status_code=401,
                    detail="Akun tidak aktif. Hubungi administrator.",
                )
        except KeyError:
            # Kolomnya seharusnya selalu ada; bila tidak, jangan diam-diam
            # meloloskan — perlakukan sebagai tidak sah.
            raise HTTPException(
                status_code=401, detail="Invalid authentication credentials"
            )

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