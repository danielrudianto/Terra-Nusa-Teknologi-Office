from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from constants.permission_matrix import ACTIONS, MATRIX
from models.user_department_model import user_departments_table
from utils.database import database
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

    # Divisi ikut dikirim.
    #
    # Beberapa bagian layar perlu membedakan "orang keuangan" dari "orang
    # tanpa divisi yang levelnya tinggi" — keduanya lolos pemeriksaan izin
    # yang sama, tetapi bukan hal yang sama.
    divisi = await database.fetch_all(
        select(user_departments_table.c.department).where(
            user_departments_table.c.userID == current_user["id"]
        )
    )

    return {
        "level": current_user["authenticationLevel"] or 1,
        "departments": [d["department"] for d in divisi],
        "permissions": izin,
    }
