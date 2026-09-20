"""
Rute KPI.

IZINNYA MEMINJAM MODUL YANG SUDAH ADA, tidak membuat modul baru.

  * Kinerja perusahaan memakai `finance_status:read` — isinya pendapatan
    dan laba, persis kelas data yang sama dengan halaman Posisi Keuangan,
    dan pintunya sudah terpasang di sana (level 4, divisi FAT).
  * Papan antrean tidak dijaga satu modul pun di tingkat rute: tiap TAHAP
    di dalamnya diperiksa izinnya sendiri-sendiri, dengan fungsi yang sama
    yang menjaga tombolnya. Pengguna yang tidak berhak atas satu tahap pun
    menerima daftar kosong, bukan 403 — dan layarnya menyembunyikan
    bagiannya.

Modul baru akan menjadi tempat ketiga yang harus sepakat tentang siapa
boleh melihat apa, dan wilayah divisi yang terlewat sudah dua kali membuat
sebuah modul tak terjangkau siapa pun (`audit_log`, `reminder`).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from controllers.kpi_controller import KpiController
from utils.auth_utils import User, get_current_user
from utils.permission import _departments, require

router = APIRouter()


@router.get("/perusahaan")
async def kpi_perusahaan(
    current_user: Annotated[
        User, Depends(require("finance_status", "read"))
    ],
    mundur: int = Query(
        12, ge=1, le=36, description="Berapa bulan ke belakang"
    ),
):
    """
    Pendapatan, biaya, dan laba per bulan, beserta marjin jendela 12 bulan.
    """
    return await KpiController.perusahaan(mundur)


@router.get("/antrean")
async def kpi_antrean(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Dokumen yang menggantung di tiap tahap, beserta umur tunggunya.

    Divisi DIBACA DI SINI, tidak diambil dari objek pengguna: objek yang
    dikembalikan autentikasi tidak memuat divisi sama sekali, dan
    membacanya dari sana selalu menghasilkan kosong — setiap procurement
    level 3 akan kehilangan tahap pemeriksaannya tanpa sebab yang terlihat.
    """
    level = int(current_user["authenticationLevel"] or 1)
    departemen = await _departments(current_user["id"])
    return await KpiController.antrean(current_user, level, departemen)
