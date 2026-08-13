import utils.config

from fastapi import FastAPI, HTTPException, Request
from utils.logger_utils import log_info, log_error
from contextlib import asynccontextmanager
from routes.routes import router
from fastapi.middleware.cors import CORSMiddleware
from utils.meilisearch import setup_meilisearch, sync_meilisearch
from utils.meilisearch_item import setup_master_item_meilisearch, sync_master_item_meilisearch
from utils.meilisearch_equipment import (
    setup_master_equipment_meilisearch,
    sync_master_equipment_meilisearch,
)
from utils.redis import sync_redis
from utils.database import database
from utils.redis import sync_redis
import sqlalchemy
import os
import time
import jwt
from utils.audit_context import set_current_user, clear_current_user

log_info("Testing logger functionality")

log_info(f"Currently using {sqlalchemy.__version__}")

# Set the lifespan of the application
@asynccontextmanager
async def lifespan(app: FastAPI):
    log_info("Lifespan function started")  # Debug log
    # Startup logic
    try:
        await database.connect()
        log_info("Database connected successfully!")
    except Exception as e:
        log_error(f"Error connecting to database: {e}")
        
    try:
        await setup_meilisearch()
        log_info("Meilisearch setup completed successfully!")
    except Exception as e:
        log_error(f"Error connecting to meilisearch: {e}")

    try:
        await sync_meilisearch()
        # Pengaturan indeks (termasuk sortableAttributes) harus diterapkan
        # sebelum data disinkronkan; tanpa ini pengurutan ditolak Meilisearch.
        await setup_master_item_meilisearch()
        await sync_master_item_meilisearch()
        # Indeks alat sewa sebelumnya tidak pernah ikut disegarkan, sehingga
        # pencarian alat memakai data lama sampai di-sync manual.
        await setup_master_equipment_meilisearch()
        await sync_master_equipment_meilisearch()
        log_info("Meilisearch setup & sync completed successfully!")
    except Exception as e:
        log_error(f"Error setting up master item meilisearch: {e}")
        
    try:
        await sync_redis()
        log_info("Redis setup completed successfully!")
    except Exception as e:
        log_error(f"Error connecting to redis: {e}")
    yield  # This is where the application runs
    # Shutdown logic
    await database.disconnect()
    log_info("Database disconnected successfully!")


# Create an instance of the FastAPI application
app = FastAPI(lifespan=lifespan, redirect_slashes=True)

# Ambang permintaan lambat, dalam milidetik.
#
# Dibuat dapat diatur lewat lingkungan supaya bisa diperketat sementara saat
# menelusuri sesuatu, tanpa mengubah kode dan menyalakan ulang dengan versi
# berbeda.
AMBANG_LAMBAT_MS = int(os.getenv("SLOW_REQUEST_MS", "800"))


@app.middleware("http")
async def slow_request_middleware(request: Request, call_next):
    """
    Catat permintaan yang lebih lambat dari ambang.

    Dipasang karena sebelumnya tidak ada satu pun ukuran waktu di sistem ini:
    ketika ada yang melapor "lemot", tidak ada cara mengetahui bagian mana
    yang lambat, dan perbaikan apa pun menjadi tebakan.

    Hanya yang melewati ambang yang dicatat. Mencatat semua permintaan
    membuat berkas log penuh oleh yang normal, dan yang lambat justru
    tenggelam di antaranya.

    Header `X-Response-Time-ms` selalu dikirim, sehingga durasinya juga
    terbaca langsung dari panel jaringan peramban tanpa membuka log server.
    """
    mulai = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # Permintaan yang gagal tetap diukur: yang lambat LALU gagal adalah
        # gejala yang paling perlu terlihat, misalnya kueri yang kehabisan
        # waktu tunggu.
        lama_ms = (time.perf_counter() - mulai) * 1000
        log_error(
            f"[lambat] {request.method} {request.url.path} "
            f"{lama_ms:.0f}ms GAGAL"
        )
        raise

    lama_ms = (time.perf_counter() - mulai) * 1000
    response.headers["X-Response-Time-ms"] = f"{lama_ms:.0f}"

    if lama_ms >= AMBANG_LAMBAT_MS:
        kueri = str(request.url.query)[:120]
        log_info(
            f"[lambat] {request.method} {request.url.path}"
            f"{('?' + kueri) if kueri else ''} "
            f"{lama_ms:.0f}ms status={response.status_code}"
        )
    return response


# Add CORS middleware

@app.middleware("http")
async def audit_context_middleware(request: Request, call_next):
    """
    Simpan identitas pengguna untuk pencatatan jejak audit.

    Diambil dari token yang sama dengan autentikasi, tanpa kueri basis data
    tambahan. Token tidak sah cukup diabaikan: middleware ini hanya melengkapi
    catatan audit, penolakan akses tetap ditangani get_current_user.
    """
    set_current_user(None, None, None)
    try:
        header = request.headers.get("authorization") or ""
        if header.lower().startswith("bearer "):
            payload = jwt.decode(
                header[7:], os.getenv("SECRET_KEY"), algorithms=["HS256"]
            )
            set_current_user(
                payload.get("user_id"),
                payload.get("name") or payload.get("sub"),
                request.client.host if request.client else None,
            )
    except Exception:
        pass

    try:
        return await call_next(request)
    finally:
        clear_current_user()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with specific origins for production
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Include the router
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=7500, reload=True, workers=1)