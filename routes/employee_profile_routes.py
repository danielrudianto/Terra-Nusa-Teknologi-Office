from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from repository.employee_profile_repository import EmployeeProfileRepository
from schemas.employee_profile_schema import EmployeeProfileSave
from utils.auth_utils import User
from utils.errors import error_detail
from utils.logger_utils import log_error
from utils.permission import require

router = APIRouter()


@router.get("/pending")
async def daftar_belum_isi(
    user: Annotated[User, Depends(require("employee_profile", "read"))],
):
    """
    Karyawan aktif yang belum punya profil.

    Ditaruh SEBELUM rute `/{employee_id}` dengan sengaja: FastAPI mencocokkan
    rute berurutan, dan bila di bawah, "pending" akan tertangkap sebagai
    employee_id lalu gagal sebagai bilangan.
    """
    hasil = await EmployeeProfileRepository.missing_profiles()
    if isinstance(hasil, dict) and "error" in hasil:
        log_error(f"Error listing employees without profile: {hasil['error']}")
        raise HTTPException(status_code=hasil["status"], detail=error_detail(hasil))
    return hasil


@router.get("/{employee_id}")
async def ambil_profil(
    employee_id: int,
    user: Annotated[User, Depends(require("employee_profile", "read"))],
):
    """
    Profil satu karyawan.

    Mengembalikan `null` bila belum pernah diisi — bukan 404. Karyawan yang
    sudah ada sebelum tabel ini dibuat memang belum punya profil, dan
    layarnya perlu menampilkan formulir kosong, bukan pesan galat.
    """
    hasil = await EmployeeProfileRepository.get_by_employee(employee_id)
    if isinstance(hasil, dict) and "error" in hasil:
        log_error(f"Error fetching employee profile: {hasil['error']}")
        raise HTTPException(status_code=hasil["status"], detail=error_detail(hasil))
    return hasil


@router.put("/{employee_id}")
async def simpan_profil(
    employee_id: int,
    payload: EmployeeProfileSave,
    user: Annotated[User, Depends(require("employee_profile", "update"))],
):
    """
    Simpan profil; dibuat bila belum ada, diperbarui bila sudah.

    Memakai PUT, bukan POST, karena satu karyawan hanya punya satu profil —
    memanggilnya dua kali dengan isi yang sama menghasilkan keadaan yang
    sama, bukan dua baris.
    """
    data = payload.model_dump(exclude_unset=True)
    # Tanggal dan daftar berulang perlu bentuk yang dapat disimpan MySQL.
    if data.get("ktpValidUntil") is not None:
        data["ktpValidUntil"] = data["ktpValidUntil"]
    for kunci in ("formalEducation", "workExperience"):
        if data.get(kunci) is not None:
            import json

            data[kunci] = json.dumps(data[kunci], default=str)

    hasil = await EmployeeProfileRepository.upsert(employee_id, data, user["id"])
    if "error" in hasil:
        log_error(f"Error saving employee profile: {hasil['error']}")
        raise HTTPException(status_code=hasil["status"], detail=error_detail(hasil))
    return hasil
