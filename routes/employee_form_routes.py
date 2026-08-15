from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from repository.employee_form_repository import EmployeeFormRepository
from utils.auth_utils import User
from utils.errors import error_detail
from utils.logger_utils import log_error
from utils.permission import require

router = APIRouter()


class VersiBaru(BaseModel):
    """Periode baru. `fields` boleh kosong; susunan bawaan yang dipakai."""

    period: str = Field(..., max_length=50)
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    fields: Optional[Dict[str, Any]] = None
    isActive: bool = True


class Jawaban(BaseModel):
    answers: Dict[str, Any]


def _periksa(hasil):
    if isinstance(hasil, dict) and "error" in hasil:
        log_error(f"Employee form error: {hasil['error']}")
        raise HTTPException(status_code=hasil["status"], detail=error_detail(hasil))
    return hasil


@router.get("/versions")
async def daftar_versi(
    user: Annotated[User, Depends(require("employee_form", "read"))],
):
    return _periksa(await EmployeeFormRepository.list_versions())


@router.get("/versions/active")
async def versi_aktif(
    user: Annotated[User, Depends(require("employee_form", "read"))],
):
    """
    Versi yang sedang berlaku; `null` bila belum ada.

    Ditaruh sebelum rute ber-parameter: FastAPI mencocokkan berurutan, dan
    "active" akan tertangkap sebagai angka bila di bawah.
    """
    return _periksa(await EmployeeFormRepository.active_version())


@router.post("/versions")
async def buat_versi(
    payload: VersiBaru,
    user: Annotated[User, Depends(require("employee_form", "create"))],
):
    return _periksa(
        await EmployeeFormRepository.create_version(
            payload.model_dump(exclude_unset=True), user["id"]
        )
    )


@router.get("/versions/{version_id}/pending")
async def belum_mengisi(
    version_id: int,
    user: Annotated[User, Depends(require("employee_form", "read"))],
):
    """Karyawan aktif yang belum mengisi periode ini."""
    return _periksa(await EmployeeFormRepository.pending(version_id))


@router.get("/{employee_id}/riwayat")
async def riwayat_pembaruan(
    employee_id: int,
    user: Annotated[User, Depends(require("employee_form", "read"))],
):
    """
    Riwayat pembaruan data seorang karyawan, terbaru lebih dulu.

    Ditaruh SEBELUM `/{employee_id}/{version_id}`: FastAPI mencocokkan
    berurutan, dan "riwayat" akan tertangkap sebagai id versi bila di bawah.
    """
    return _periksa(await EmployeeFormRepository.riwayat(employee_id))


@router.get("/{employee_id}/{version_id}")
async def ambil_jawaban(
    employee_id: int,
    version_id: int,
    user: Annotated[User, Depends(require("employee_form", "read"))],
):
    """Jawaban satu karyawan; `null` bila belum mengisi."""
    return _periksa(
        await EmployeeFormRepository.get_submission(employee_id, version_id)
    )


@router.put("/{employee_id}/{version_id}")
async def simpan_jawaban(
    employee_id: int,
    version_id: int,
    payload: Jawaban,
    user: Annotated[User, Depends(require("employee_form", "update"))],
):
    """
    Simpan jawaban.

    Dapat diperbarui kapan saja dalam periodenya: siklusnya setahun, tetapi
    kontak darurat yang berubah di tengah tahun tidak boleh menunggu sampai
    pengisian berikutnya.
    """
    return _periksa(
        await EmployeeFormRepository.save_submission(
            employee_id, version_id, payload.answers, user["id"]
        )
    )
