from typing import Annotated

from fastapi import APIRouter, Depends

from constants.permission_matrix import ACTIONS, MATRIX
from utils.auth_utils import User, get_current_user
from utils.permission import is_allowed

router = APIRouter()

"""
Izin efektif pengguna yang sedang masuk.

Dipakai sisi layar untuk menyembunyikan menu dan tombol. Matriksnya sengaja
TIDAK disalin ke frontend karena dua alasan:

  1. Matriks yang hidup di dua tempat pasti melenceng suatu saat, dan yang
     melenceng diam-diam adalah yang paling berbahaya.
  2. Izin khusus per pengguna tidak dapat disimpulkan dari level. Slip gaji
     bernilai 9 pada matriks — tidak pernah terbuka lewat level mana pun —
     sehingga tanpa hasil hitungan dari sini, menu gaji tidak akan pernah
     tampil bahkan bagi yang sudah diberi izin khusus.

Menyembunyikan tombol bukan pengamanan; pemeriksaan di rute tetap yang
menentukan. Ini hanya agar pengguna tidak menekan tombol yang pasti ditolak.
"""


@router.get("/me")
async def get_my_permissions(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Peta izin: {modul: {aksi: boleh}}.

    Sengaja tanpa `require()` — setiap pengguna berhak mengetahui haknya
    sendiri, dan menutupnya justru membuat layar tidak dapat menampilkan
    apa pun.
    """
    izin: dict[str, dict[str, bool]] = {}
    for modul in MATRIX:
        izin[modul] = {
            aksi: await is_allowed(current_user, modul, aksi) for aksi in ACTIONS
        }

    return {
        "level": current_user["authenticationLevel"] or 1,
        "permissions": izin,
    }
