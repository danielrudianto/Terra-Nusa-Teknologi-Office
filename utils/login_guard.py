import time

from utils.logger_utils import log_error
from utils.redis import r

"""
Pembatas percobaan masuk.

Tanpa pembatasan, kata sandi bisa ditebak berulang kali tanpa henti. Bcrypt
memang lambat, tetapi itu memperlambat penebakan — bukan menghentikannya.

Hitungan disimpan di Redis yang sudah dipakai aplikasi, jadi tidak menambah
komponen baru. Bila Redis sedang tidak tersedia, pembatas dilewati: menolak
semua login karena Redis mati akan mengunci seluruh pengguna dari sistemnya
sendiri.
"""

# Batas per akun (email) dan per alamat IP.
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60
WINDOW_SECONDS = 15 * 60


def _key(jenis: str, nilai: str) -> str:
    return f"login_attempt:{jenis}:{str(nilai).strip().lower()}"


def _sisa_kunci(kunci: str) -> int:
    """Sisa detik penguncian; 0 bila tidak terkunci."""
    try:
        jumlah = r.get(kunci)
        if jumlah is None or int(jumlah) < MAX_ATTEMPTS:
            return 0
        sisa = r.ttl(kunci)
        return sisa if sisa and sisa > 0 else 0
    except Exception as e:
        log_error(f"Rate limit tidak dapat dibaca: {str(e)}")
        return 0


def cek_terkunci(email: str, ip: str = None) -> int:
    """
    Kembalikan sisa detik penguncian, atau 0 bila boleh mencoba.

    Diperiksa SEBELUM kata sandi dicocokkan, supaya percobaan yang sudah
    melewati batas tidak membebani proses hashing.
    """
    sisa = _sisa_kunci(_key("email", email))
    if ip:
        sisa = max(sisa, _sisa_kunci(_key("ip", ip)))
    return sisa


def catat_gagal(email: str, ip: str = None) -> None:
    """Tambah hitungan gagal; jendela dihitung sejak percobaan pertama."""
    try:
        for kunci in [_key("email", email)] + ([_key("ip", ip)] if ip else []):
            jumlah = r.incr(kunci)
            if jumlah == 1:
                r.expire(kunci, WINDOW_SECONDS)
            elif jumlah == MAX_ATTEMPTS:
                # Begitu batas tercapai, masa tunggu dimulai dari sekarang.
                r.expire(kunci, LOCKOUT_SECONDS)
    except Exception as e:
        log_error(f"Rate limit tidak dapat dicatat: {str(e)}")


def bersihkan(email: str, ip: str = None) -> None:
    """Hapus hitungan setelah berhasil masuk."""
    try:
        r.delete(_key("email", email))
        if ip:
            r.delete(_key("ip", ip))
    except Exception as e:
        log_error(f"Rate limit tidak dapat dibersihkan: {str(e)}")