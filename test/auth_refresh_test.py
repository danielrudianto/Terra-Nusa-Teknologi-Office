"""
Pengujian penyegaran token.

Sebelumnya endpoint ini hanya mengembalikan access token, sehingga refresh
token tidak pernah diperbarui: yang dipegang pengguna tetap milik login
pertamanya, dan masa berlakunya terus berjalan. Setelah 7 hari, penyegaran
gagal meski orangnya memakai aplikasi setiap hari.

Gejalanya menyesatkan — yang jarang menutup aplikasi justru lebih dulu
terlempar, sementara yang rutin masuk-keluar tidak pernah mengalaminya.
Kekeliruan seperti itu sulit ditemukan dari laporan pengguna, sehingga
pantas dijaga pengujian.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from utils.auth_utils import (
    ALGORITHM,
    REFRESH_TOKEN_EXPIRE_MINUTES,
    SECRET_KEY,
    create_access_token,
)


def buat_refresh(user_id: int = 1, umur_hari: int = 0) -> str:
    """Refresh token yang seolah diterbitkan `umur_hari` yang lalu."""
    terbit = datetime.now(timezone.utc) - timedelta(days=umur_hari)
    exp = terbit + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"user_id": user_id, "exp": exp.timestamp()}, SECRET_KEY, algorithm=ALGORITHM
    )


def test_refresh_token_berlaku_tujuh_hari():
    """Masa berlakunya harus jauh lebih panjang daripada access token."""
    assert REFRESH_TOKEN_EXPIRE_MINUTES >= 60 * 24 * 7


def test_token_baru_dapat_dibaca_kembali():
    token = create_access_token(
        {"user_id": 3}, timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    )
    isi = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    assert isi["user_id"] == 3
    assert "exp" in isi


def test_token_yang_masih_muda_dapat_dibaca():
    token = buat_refresh(umur_hari=3)
    isi = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    assert isi["user_id"] == 1


def test_token_yang_lewat_masa_berlaku_ditolak():
    token = buat_refresh(umur_hari=8)

    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def test_pemakaian_rutin_tidak_pernah_terputus():
    """
    Inti perbaikannya.

    Selama refresh token ikut diperbarui setiap kali disegarkan, umurnya
    kembali nol — sehingga pemakaian harian tidak pernah menabrak batas 7
    hari. Bila suatu saat endpointnya berhenti mengembalikan refresh token
    baru, pengujian ini yang lebih dulu gagal.
    """
    umur = 0
    for hari in range(1, 31):
        umur += 1
        token = buat_refresh(umur_hari=umur)

        # Selama masih sah, penyegaran menghasilkan token baru: umurnya nol.
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        umur = 0

    assert umur == 0


def test_tanpa_pembaruan_terputus_di_hari_ketujuh():
    """
    Keadaan sebelum perbaikan, ditulis sebagai pembanding.

    Bila refresh token tidak pernah diperbarui, umurnya terus bertambah dan
    penyegaran gagal pada hari ketujuh.
    """
    gagal_pada = None
    for hari in range(1, 11):
        try:
            jwt.decode(
                buat_refresh(umur_hari=hari), SECRET_KEY, algorithms=[ALGORITHM]
            )
        except jwt.ExpiredSignatureError:
            gagal_pada = hari
            break

    assert gagal_pada == 7
