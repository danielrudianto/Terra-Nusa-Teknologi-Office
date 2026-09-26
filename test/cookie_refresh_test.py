"""
REFRESH TOKEN SEBAGAI COOKIE HttpOnly.

Dulu ia dikembalikan di badan jawaban dan disimpan layar di `localStorage`.
`localStorage` terbuka bagi skrip mana pun yang berhasil berjalan di halaman
— satu XSS di layar mana pun, satu paket pihak ketiga yang disusupi, dan
kuncinya ikut terbawa. Dan ia kunci yang paling mahal di sistem ini: ia
menerbitkan token akses baru berulang kali selama tujuh hari, tanpa kata
sandi, tanpa terlihat sebagai login baru.

Yang dijaga di sini bukan "ada cookie-nya", melainkan hal-hal yang bila
salah TIDAK menimbulkan galat sama sekali:

  * `httponly` menyala — tanpanya seluruh perubahan ini tidak ada artinya;
  * cookie DIPERBARUI tiap penyegaran, bukan hanya saat login;
  * `/logout` benar-benar menghapusnya — layar tidak bisa, itu inti HttpOnly;
  * atribut penghapusan SAMA dengan atribut pemasangan, kalau tidak cookie
    lamanya tetap tinggal dan yang "keluar" masih dapat menyegarkan token;
  * header lama masih diterima selama masa peralihan, supaya tab yang sudah
    terbuka saat deploy tidak terlempar serentak.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Response

import routes.auth_routes as auth


class _Permintaan:
    """Request secukupnya: cookie dan header."""

    def __init__(self, cookies=None, headers=None):
        self.cookies = cookies or {}
        self.headers = headers or {}
        self.client = None


def _cookie_terpasang(response: Response, nama: str = "refresh_token"):
    """Header `set-cookie` untuk nama tertentu, sebagai teks."""
    for kunci, nilai in response.raw_headers:
        if kunci.decode().lower() == "set-cookie":
            teks = nilai.decode()
            if teks.startswith(f"{nama}="):
                return teks
    return None


def _token_sah(user_id: int = 1) -> str:
    now = datetime.now(timezone.utc)
    return auth.create_access_token(
        {"user_id": user_id, "name": "Uji", "iat": int(now.timestamp())},
        timedelta(minutes=60),
    )


# ---------------------------------------------------------------------------
# Bentuk cookie-nya
# ---------------------------------------------------------------------------


def test_cookie_httponly_dan_berjalur_auth():
    r = Response()
    auth._pasang_cookie_segar(r, "abc")
    teks = _cookie_terpasang(r)
    assert teks is not None, "cookie tidak dipasang sama sekali"
    rendah = teks.lower()
    # INTI SELURUH PERUBAHAN. Tanpa ini, cookie-nya sama terbukanya dengan
    # `localStorage` — hanya berpindah tempat.
    assert "httponly" in rendah
    # Jalurnya dipersempit: cookie ini hanya diperlukan rute penyegaran dan
    # keluar. Mengirimkannya pada tiap permintaan gambar dan daftar hanya
    # memperluas permukaan tanpa gunanya.
    assert "path=/auth" in rendah
    assert "samesite=lax" in rendah


def test_cookie_tidak_menyebar_ke_seluruh_subdomain():
    # TANPA `domain`. Cookie diterbitkan host API dan dikirim kembali ke host
    # itu juga; `domain=.terrabot...` justru menyebarkannya ke subdomain yang
    # tidak ada urusannya dengan autentikasi.
    r = Response()
    auth._pasang_cookie_segar(r, "abc")
    assert "domain=" not in _cookie_terpasang(r).lower()


def test_secure_menyala_di_produksi_dan_mati_di_luar_itu(monkeypatch):
    # Di produksi wajib; di `http://localhost` justru harus mati — peramban
    # membuang cookie `Secure` pada koneksi biasa DIAM-DIAM, dan yang terlihat
    # hanyalah "sesi berakhir" setiap satu jam.
    monkeypatch.setenv("APP_ENV", "production")
    r = Response()
    auth._pasang_cookie_segar(r, "abc")
    assert "secure" in _cookie_terpasang(r).lower()

    monkeypatch.setenv("APP_ENV", "development")
    r2 = Response()
    auth._pasang_cookie_segar(r2, "abc")
    assert "secure" not in _cookie_terpasang(r2).lower()


def test_penghapusan_memakai_atribut_yang_SAMA(monkeypatch):
    """
    Peramban mencocokkan nama, path, dan domain saat menghapus.

    Berbeda satu saja, cookie lamanya tetap tinggal — dan yang menekan
    "keluar" masih memegang kunci yang dapat menerbitkan token akses baru
    selama tujuh hari. Tidak ada galat, dan tidak ada satu pun layar yang
    menunjukkannya.
    """
    monkeypatch.setenv("APP_ENV", "production")
    pasang = Response()
    auth._pasang_cookie_segar(pasang, "abc")
    hapus = Response()
    auth._hapus_cookie_segar(hapus)

    def atribut(teks):
        bagian = [b.strip().lower() for b in teks.split(";")[1:]]
        return {b for b in bagian if not b.startswith(("expires", "max-age"))}

    assert atribut(_cookie_terpasang(pasang)) == atribut(_cookie_terpasang(hapus))


# ---------------------------------------------------------------------------
# Dari mana tokennya dibaca
# ---------------------------------------------------------------------------


def test_cookie_didahulukan_atas_header():
    r = _Permintaan(
        cookies={"refresh_token": "dari-cookie"},
        headers={"x-refresh-token": "Bearer dari-header"},
    )
    assert auth._baca_token_segar(r) == "dari-cookie"


def test_header_lama_MASIH_diterima_selama_peralihan():
    # Tab yang sudah terbuka sebelum deploy masih memegang tokennya di
    # `localStorage`. Tanpa cadangan ini mereka terlempar serentak saat
    # deploy, dan yang mereka lihat hanyalah "sesi berakhir" tanpa sebab.
    r = _Permintaan(headers={"x-refresh-token": "Bearer dari-header"})
    assert auth._baca_token_segar(r) == "dari-header"


def test_tanpa_keduanya_mengembalikan_kosong():
    assert auth._baca_token_segar(_Permintaan()) == ""
    # Header tanpa skema "Bearer " bukan token.
    assert auth._baca_token_segar(_Permintaan(headers={"x-refresh-token": "abc"})) == ""


# ---------------------------------------------------------------------------
# Rutenya
# ---------------------------------------------------------------------------


def test_refresh_menerbitkan_cookie_BARU_tiap_kali():
    """
    Cookie ikut diperbarui tiap penyegaran, bukan hanya saat login.

    Tanpa itu cookie-nya tetap milik login pertama dan kedaluwarsa tujuh hari
    kemudian walau orangnya memakai aplikasi setiap hari — persis cacat yang
    dulu terjadi pada refresh token di badan jawaban.
    """
    r = Response()
    permintaan = _Permintaan(cookies={"refresh_token": _token_sah()})
    hasil = asyncio.run(auth.refresh_token(permintaan, r))

    teks = _cookie_terpasang(r)
    assert teks is not None, "penyegaran tidak memperbarui cookie-nya"
    assert "httponly" in teks.lower()
    nilai_baru = teks.split(";")[0].split("=", 1)[1]
    assert nilai_baru, "cookie barunya kosong"
    assert nilai_baru == hasil["refresh_token"]


def test_refresh_tanpa_token_ditolak_401():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as e:
        asyncio.run(auth.refresh_token(_Permintaan(), Response()))
    assert e.value.status_code == 401


def test_logout_menghapus_cookie_dan_tidak_menuntut_token():
    """
    Tidak menuntut token yang sah — dan itu disengaja.

    Yang menekan keluar justru sering sedang terlempar karena tokennya sudah
    tidak berlaku. Menolak permintaannya berarti meninggalkan cookie-nya di
    peramban, yaitu kebalikan dari yang diminta.
    """
    r = Response()
    hasil = asyncio.run(auth.logout(r))
    assert hasil == {"ok": True}
    teks = _cookie_terpasang(r)
    assert teks is not None
    # Dihapus = dipasang kosong dengan masa yang sudah lewat.
    assert teks.split(";")[0] in ("refresh_token=", 'refresh_token=""')
