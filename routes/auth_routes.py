import os

from fastapi import APIRouter, HTTPException, Request, Response
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


# ---------------------------------------------------------------------------
# REFRESH TOKEN DISIMPAN SEBAGAI COOKIE HttpOnly, BUKAN DI localStorage.
# ---------------------------------------------------------------------------
#
# `localStorage` dapat dibaca JavaScript mana pun yang berhasil berjalan di
# halaman — satu skrip pihak ketiga yang disusupi, satu XSS di layar mana
# pun, dan refresh token ikut terbawa. Refresh token adalah kunci yang
# paling mahal di sistem ini: ia menerbitkan access token baru berulang kali
# selama tujuh hari, jadi yang mencurinya tidak perlu kata sandi dan tidak
# terlihat sebagai login baru.
#
# Cookie `HttpOnly` TIDAK dapat dibaca JavaScript sama sekali. Ia tetap
# terkirim sendiri oleh peramban pada permintaan ke host yang menerbitkannya.
#
# ATURAN COOKIE-NYA, dan tiap bagian ada alasannya:
#
#   httponly  — inti seluruh perubahan ini.
#   secure    — hanya lewat HTTPS. Dimatikan di luar produksi supaya
#               pengembangan di `http://localhost` tetap jalan; kalau tidak,
#               peramban membuang cookie-nya diam-diam dan yang terlihat
#               hanyalah "sesi berakhir" tiap satu jam.
#   samesite  — `lax`. Aplikasi (`terrabot.…`) dan API (`services.terrabot.…`)
#               berbagi domain terdaftar yang sama, sehingga permintaannya
#               SAME-SITE walau beda asal. `strict` pun sebenarnya cukup,
#               tetapi `lax` menyisakan ruang bila kelak ada tautan masuk.
#   path      — `/auth` saja. Cookie ini hanya diperlukan rute penyegaran dan
#               keluar; mengirimkannya pada setiap permintaan gambar dan
#               daftar hanya memperluas permukaan tanpa gunanya.
#
# TANPA `domain`, SENGAJA. Cookie diterbitkan oleh host API dan dikirim
# kembali ke host API itu juga. Memberi `domain=.terrabot.…` justru
# menyebarkannya ke seluruh subdomain, termasuk yang tidak ada urusannya.
#
# Sisi peramban wajib mengirim `withCredentials`, dan CORS di `main.py`
# sudah `allow_credentials=True` dengan daftar asal yang disebut satu per
# satu — bukan `*`, yang memang tidak diizinkan bersama kredensial.

NAMA_COOKIE_SEGAR = "refresh_token"
JALUR_COOKIE_SEGAR = "/auth"


def _produksi() -> bool:
    return (os.getenv("APP_ENV") or "").strip().lower() == "production"


def _pasang_cookie_segar(response: Response, token: str) -> None:
    response.set_cookie(
        key=NAMA_COOKIE_SEGAR,
        value=token,
        httponly=True,
        secure=_produksi(),
        samesite="lax",
        path=JALUR_COOKIE_SEGAR,
        max_age=int(REFRESH_TOKEN_EXPIRE_MINUTES) * 60,
    )


def _hapus_cookie_segar(response: Response) -> None:
    # Atributnya HARUS sama dengan saat dipasang — peramban mencocokkan
    # nama, path, dan domain. Berbeda satu saja, cookie lamanya tetap
    # tinggal dan yang "keluar" masih dapat menyegarkan tokennya.
    response.delete_cookie(
        key=NAMA_COOKIE_SEGAR,
        path=JALUR_COOKIE_SEGAR,
        httponly=True,
        secure=_produksi(),
        samesite="lax",
    )


def _baca_token_segar(request: Request) -> str:
    """
    Refresh token dari COOKIE lebih dulu, header sebagai cadangan.

    Cadangannya SENGAJA dipertahankan untuk masa peralihan: tab yang sudah
    terbuka sebelum pembaruan ini masih memegang tokennya di `localStorage`
    dan mengirimkannya lewat header. Tanpa cadangan ini mereka semua
    terlempar keluar serentak pada saat deploy — dan yang terlihat oleh
    mereka hanyalah "sesi berakhir" tanpa sebab.

    Begitu seluruh pengguna sudah masuk kembali (paling lama tujuh hari,
    sepanjang masa refresh token), cabang headernya dapat dibuang.
    """
    dari_cookie = (request.cookies.get(NAMA_COOKIE_SEGAR) or "").strip()
    if dari_cookie:
        return dari_cookie
    header = request.headers.get("x-refresh-token") or ""
    bagian = header.split(" ")
    return bagian[1].strip() if len(bagian) > 1 else ""

@router.post("/")
async def login(loginData: LoginData, request: Request, response: Response):
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
    
    # BERZONA, bukan `utcnow()` yang naif.
    #
    # `datetime.utcnow()` mengembalikan waktu UTC TANPA zona, dan
    # `.timestamp()` atas waktu tanpa zona ditafsirkan Python sebagai waktu
    # LOKAL mesin. Selama server berjalan pada UTC, keduanya kebetulan sama
    # dan tidak ada yang terlihat keliru.
    #
    # Begitu zona servernya disetel ke WIB, `iat` dan `exp` bergeser TUJUH
    # JAM ke belakang — dan setiap access token lahir dalam keadaan sudah
    # kedaluwarsa. Bukan satu orang gagal masuk, melainkan tidak seorang pun
    # dapat masuk, dan galatnya cuma "sesi berakhir".
    #
    # Rute penyegaran token di bawah sudah memakai bentuk berzona; hanya
    # penerbitan token saat login yang tertinggal.
    now = datetime.now(timezone.utc)

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
    
    _pasang_cookie_segar(response, refresh_token)

    """
    `refresh_token` MASIH ikut di badan jawaban — sementara.

    Layar yang baru tidak menyimpannya lagi; ia mengandalkan cookie. Bidang
    ini ditinggalkan supaya build layar yang LAMA — yang masih terbuka di
    tab seseorang saat deploy — tidak mendadak gagal masuk.

    Dibuang pada pembersihan berikutnya, bersama cabang header pada
    `_baca_token_segar`. Keduanya berpasangan; membuang salah satunya lebih
    dulu meninggalkan jalan masuk yang tidak dipakai siapa pun.
    """
    return {"access_token": token, "refresh_token": refresh_token, "token_type": "bearer", "user": user}
    
@router.post("/refresh")
async def refresh_token(request: Request, response: Response):
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
    refresh_token = _baca_token_segar(request)
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

    # BERPUTAR: tiap penyegaran menerbitkan cookie baru berikut masa baru.
    # Tanpa ini, cookie-nya tetap milik login pertama dan kedaluwarsa tujuh
    # hari kemudian walau orangnya memakai aplikasi setiap hari — persis
    # cacat yang dahulu terjadi pada refresh token di badan jawaban.
    _pasang_cookie_segar(response, new_refresh)

    return {
        "access_token": token_data,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(response: Response):
    """
    Hapus cookie refresh token.

    WAJIB ADA sejak cookie-nya `HttpOnly`: layar tidak dapat menghapusnya
    sendiri — itu memang intinya. Tanpa rute ini, "keluar" hanya membuang
    access token di layar, sementara kunci yang paling mahal tetap tinggal
    di peramban dan masih dapat menerbitkan token baru selama tujuh hari.

    TIDAK menuntut token yang sah. Yang menekan keluar mungkin justru
    sedang terlempar karena tokennya sudah tidak berlaku, dan menolak
    permintaannya berarti meninggalkan cookie-nya di sana.
    """
    _hapus_cookie_segar(response)
    return {"ok": True}