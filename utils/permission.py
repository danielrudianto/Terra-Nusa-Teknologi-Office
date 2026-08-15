import time
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import select

from constants.permission_matrix import (
    NOT_APPLICABLE,
    SPECIAL_ONLY,
    required_level,
)
from constants.department_modules import modules_for
from models.user_department_model import user_departments_table
from models.user_permission_model import user_permissions_table
from utils.auth_utils import get_current_user
from utils.database import database
from utils.logger_utils import log_error

"""
Pemeriksa izin.

Urutan penentuan:

    1. Izin khusus pengguna (bila ada) -> nilainya menang, izin maupun larangan
    2. Modul harus berada dalam wilayah departemen pengguna
    3. Level pengguna dibanding level minimum modul

Level dan departemen menjawab hal berbeda: level menentukan sejauh apa yang
boleh dilakukan, departemen menentukan modul mana yang menjadi urusannya.
Tanpa sumbu departemen, level 1 procurement dan level 1 accounting terpaksa
melihat hal yang sama padahal pekerjaannya berbeda.

Menyembunyikan tombol di layar bukan pengamanan; pemeriksaan di sinilah yang
menentukan. Setiap rute yang mengubah data harus melewatinya.
"""

# Izin khusus jarang berubah, sementara satu layar bisa memicu banyak
# permintaan. Hasilnya disimpan sebentar agar tidak menambah satu query pada
# setiap permintaan.
_CACHE: dict[int, tuple[float, dict[tuple[str, str], bool]]] = {}
_DEPT_CACHE: dict[int, tuple[float, set[str]]] = {}
_CACHE_TTL = 60.0

#: Modul yang batas divisinya berlaku untuk SEMUA level di bawah 5, termasuk
#: yang tidak punya departemen. Isinya data paling sensitif di sistem.
MODUL_WILAYAH_MUTLAK = frozenset(
    {"salary_slip", "employees", "employee_profile", "employee_form"}
)


def invalidate_permission_cache(user_id: int | None = None) -> None:
    """
    Dipanggil setelah izin diubah agar perubahannya langsung berlaku dan tidak
    menunggu masa simpan habis.
    """
    if user_id is None:
        _CACHE.clear()
        _DEPT_CACHE.clear()
    else:
        _CACHE.pop(user_id, None)
        _DEPT_CACHE.pop(user_id, None)


async def _overrides(user_id: int) -> dict[tuple[str, str], bool]:
    cached = _CACHE.get(user_id)
    if cached and (time.monotonic() - cached[0]) < _CACHE_TTL:
        return cached[1]

    try:
        rows = await database.fetch_all(
            select(user_permissions_table).where(
                user_permissions_table.c.userID == user_id
            )
        )
        data = {(r["module"], r["action"]): bool(r["allowed"]) for r in rows}
    except Exception as e:
        # Bila tabel izin tidak terbaca, jangan menganggap semuanya boleh:
        # kembalikan kosong sehingga penentuan jatuh ke level pengguna.
        log_error(f"Izin khusus tidak dapat dibaca: {str(e)}")
        return {}

    _CACHE[user_id] = (time.monotonic(), data)
    return data


async def _departments(user_id: int) -> set[str]:
    cached = _DEPT_CACHE.get(user_id)
    if cached and (time.monotonic() - cached[0]) < _CACHE_TTL:
        return cached[1]

    try:
        rows = await database.fetch_all(
            select(user_departments_table).where(
                user_departments_table.c.userID == user_id
            )
        )
        data = {r["department"] for r in rows}
    except Exception as e:
        # Tabel belum ada atau tidak terbaca. Dikembalikan kosong, yang
        # artinya penentuan jatuh sepenuhnya ke level — perilaku sebelum
        # departemen diperkenalkan.
        log_error(f"Departemen pengguna tidak dapat dibaca: {str(e)}")
        return set()

    _DEPT_CACHE[user_id] = (time.monotonic(), data)
    return data


async def is_allowed(user, module: str, action: str) -> bool:
    """Apakah pengguna boleh melakukan aksi ini pada modul tersebut."""
    if user is None:
        return False

    user_id = user["id"]
    level = user["authenticationLevel"] or 1

    override = (await _overrides(user_id)).get((module, action))
    if override is not None:
        return override

    """
    Batas wilayah departemen.

    Level 5 tidak dibatasi: superadmin memang perlu melihat seluruh sistem.

    Level 4 juga tidak dibatasi. Jabatannya General Manager — wilayahnya
    seluruh perusahaan, bukan satu divisi, sehingga ia sengaja tidak diberi
    departemen. Ditulis sebagai `level < 4` agar aturannya tetap berlaku
    walaupun kelak ada level 4 yang kebetulan diberi departemen.

    Pengguna yang BELUM punya departemen sama sekali juga tidak dibatasi,
    sehingga penambahan tabel ini tidak mengunci siapa pun sebelum datanya
    diisi. Begitu seseorang diberi departemen, batas ini langsung berlaku
    baginya.
    """
    departments = await _departments(user_id)
    if level < 4 and departments and module not in modules_for(departments):
        return False

    """
    Modul yang batas divisinya BERLAKU MUTLAK.

    Slip gaji dan data karyawan hanya wilayah HRD dan FAT, dan itu tidak
    boleh terlewati hanya karena levelnya tinggi atau karena departemennya
    belum diisi. Tanpa penjagaan ini, seorang General Manager membaca gaji
    seluruh karyawan tanpa seorang pun pernah memutuskan bahwa ia boleh —
    dan daftar aktivitas sudah lebih dulu ditutup untuk level 4 justru
    supaya tidak menjadi pintu belakang ke angka yang sama.

    Bila kelak memang perlu, memberikannya cukup dengan memasukkan orangnya
    ke divisi HRD atau memberi izin khusus. Bedanya: cara itu meninggalkan
    keputusan yang tercatat, bukan akses yang diam-diam ada.
    """
    if level < 5 and module in MODUL_WILAYAH_MUTLAK:
        if not departments or module not in modules_for(departments):
            return False

    minimum = required_level(module, action)
    if minimum in (NOT_APPLICABLE, SPECIAL_ONLY):
        # Aksi yang tidak berlaku, atau yang sengaja hanya lewat izin khusus
        # (mis. slip gaji) — tidak pernah terbuka lewat level.
        return False

    return level >= minimum


def require(module: str, action: str):
    """
    Dependency FastAPI.

    Mengembalikan objek pengguna yang sama seperti `get_current_user`, sehingga
    isi rute tidak perlu diubah — cukup menukar isi `Depends`.

        async def approve(id: int, current_user = Depends(require("expenses", "approve"))):
    """

    async def _cek(current_user: Annotated[dict, Depends(get_current_user)]):
        if not await is_allowed(current_user, module, action):
            raise HTTPException(
                status_code=403,
                detail="Anda tidak memiliki akses untuk tindakan ini.",
            )
        return current_user

    return _cek

#: Level yang DIKECUALIKAN dari larangan menyetujui dokumen sendiri.
#
# General manager (4) dan pemilik (5). Keduanya memang berwenang atas seluruh
# dokumen, dan pada perusahaan sebesar ini kerap merekalah satu-satunya yang
# hadir untuk menyetujui — melarangnya berarti dokumen tertahan tanpa ada
# orang lain yang berwenang.
#
# Pengecualian ini BUKAN berarti tanpa catatan: persetujuan atas dokumen
# sendiri tetap tercatat pada jejak aktivitas, sehingga dapat ditelusuri.
LEVEL_BOLEH_SETUJU_SENDIRI = 4


def boleh_menyetujui_sendiri(level) -> bool:
    """
    Pengguna ini boleh menyetujui dokumen yang dibuatnya sendiri.

    Ditulis sekali di sini, bukan diulang di tiap controller: ambangnya
    pernah berbeda antar modul, dan yang tertinggal saat aturannya berubah
    tidak menimbulkan galat — hanya satu modul yang diam-diam lebih longgar.
    """
    try:
        return int(level or 1) >= LEVEL_BOLEH_SETUJU_SENDIRI
    except (TypeError, ValueError):
        return False
