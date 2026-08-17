"""
Ujian rekrutmen: bank soal.

Seluruh rute di berkas ini dijaga modul `hr_recruitment`, yang termasuk
`MODUL_WILAYAH_MUTLAK` — hanya divisi HRD dan pemilik. Isinya data pribadi
orang yang bahkan belum menjadi karyawan, dan jawaban yang menentukan
diterima atau tidaknya.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from controllers.hr_recruitment_controller import HrRecruitmentController
from schemas.hr_recruitment_schema import SoalCreate, SoalUpdate
from utils.auth_utils import User
from utils.errors import error_detail
from utils.permission import require

router = APIRouter()


def _periksa(hasil):
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(
            status_code=hasil.get("status", 500), detail=error_detail(hasil)
        )
    return hasil


@router.get("/tests")
async def daftar_ujian(
    user: Annotated[User, Depends(require("hr_recruitment", "read"))],
):
    """Paket ujian beserta jumlah soalnya."""
    return _periksa(await HrRecruitmentController.daftar_ujian())


@router.get("/questions")
async def daftar_soal(
    user: Annotated[User, Depends(require("hr_recruitment", "read"))],
    testID: Optional[int] = Query(None, description="Saring per paket ujian"),
    keyword: Optional[str] = Query(None, description="Cari di soal & catatan"),
):
    """Bank soal, disaring paket ujian dan kata pencarian."""
    return _periksa(
        await HrRecruitmentController.daftar_soal(testID, keyword)
    )


@router.post("/questions")
async def buat_soal(
    payload: SoalCreate,
    user: Annotated[User, Depends(require("hr_recruitment", "create"))],
):
    """Tambah satu soal; urutannya diisi otomatis di belakang yang sudah ada."""
    return _periksa(
        await HrRecruitmentController.buat_soal(payload.model_dump())
    )


@router.put("/questions/{question_id}")
async def ubah_soal(
    question_id: int,
    payload: SoalUpdate,
    user: Annotated[User, Depends(require("hr_recruitment", "update"))],
):
    """
    Ubah satu soal.

    `exclude_unset` dipakai supaya kolom yang tidak dikirim tidak tersentuh —
    tanpa itu, seluruh kolom tertimpa `None` pada setiap penyuntingan kecil.
    """
    return _periksa(
        await HrRecruitmentController.ubah_soal(
            question_id, payload.model_dump(exclude_unset=True)
        )
    )


@router.delete("/questions/{question_id}")
async def hapus_soal(
    question_id: int,
    user: Annotated[User, Depends(require("hr_recruitment", "delete"))],
):
    """
    Tandai soal terhapus; barisnya tetap ada.

    Jawaban lama menunjuk ke soal ini — menghapus barisnya membuat lembar
    jawaban yang sudah dinilai kehilangan pertanyaannya.
    """
    return _periksa(await HrRecruitmentController.hapus_soal(question_id))
