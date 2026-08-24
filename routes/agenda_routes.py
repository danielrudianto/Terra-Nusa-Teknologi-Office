from datetime import date as d
from utils.errors import ErrorCode, error_detail
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from controllers.agenda_controller import AgendaController
from models.reminder_model import REMINDER_CATEGORIES
from schemas.reminder_schema import ReminderCreate, ReminderUpdate
from utils.auth_utils import User, get_current_user
from utils.permission import require

router = APIRouter()


def _level(user) -> int:
    """
    Baca level dari objek pengguna.

    Objek yang dikembalikan `require()` berupa Record dari pustaka
    `databases`, yang TIDAK memiliki metode `.get()` — memanggilnya melempar
    AttributeError dan permintaannya gagal tanpa menyebut sebabnya.

    Bila levelnya tidak terbaca, jangan diperlakukan sebagai akses tinggi:
    yang aman adalah menganggapnya paling rendah.
    """
    try:
        return int(user["authenticationLevel"] or 1)
    except (KeyError, TypeError, ValueError):
        return 1


@router.get("/")
async def get_agenda(
    # Cukup sudah masuk. Isinya nama rekan yang berulang tahun dan pengingat
    # yang memang ditujukan kepadanya — tidak ada yang perlu dibatasi lebih
    # jauh, dan membatasinya justru menghilangkan gunanya.
    current_user: Annotated[User, Depends(get_current_user)],
    days: int = Query(7, ge=0, le=31, description="Jangkauan ke depan, dalam hari"),
):
    """Isi agenda: ulang tahun rekan dan pengingat, dalam satu permintaan."""
    result = await AgendaController.agenda(current_user["id"], d.today(), days)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result


@router.get("/range")
async def get_agenda_range(
    current_user: Annotated[User, Depends(get_current_user)],
    start: d = Query(..., description="Tanggal awal, YYYY-MM-DD"),
    end: d = Query(..., description="Tanggal akhir, YYYY-MM-DD"),
):
    """
    Isi agenda untuk rentang tanggal bebas; dipakai halaman kalender.

    Rentangnya dibatasi 62 hari. Tampilan bulanan paling banyak memuat enam
    pekan (42 hari), jadi batas itu memberi ruang tanpa membuka peluang
    permintaan yang menarik data bertahun-tahun sekaligus.
    """
    if end < start:
        raise HTTPException(
            status_code=400,
            detail={"code": ErrorCode.VALIDATION, "message": "end must not precede start."},
        )
    if (end - start).days > 62:
        raise HTTPException(
            status_code=400,
            detail={"code": ErrorCode.VALIDATION, "message": "Range must not exceed 62 days."},
        )

    result = await AgendaController.rentang(current_user["id"], start, end)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result


@router.get("/categories")
async def get_categories(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Daftar kategori yang dikenali.

    Dikirim dari sini agar layar tidak menyalin daftarnya sendiri — dua
    salinan berarti suatu saat salah satunya diperbarui sendirian, dan
    pilihan yang tampil tidak lagi sama dengan yang diterima server.
    """
    return {"categories": list(REMINDER_CATEGORIES)}


@router.get("/taggable-users")
async def get_taggable_users(
    # Cukup sudah masuk. Yang dikembalikan hanya id dan nama rekan kerja —
    # tidak ada yang perlu dibatasi, dan membatasinya dengan `user:read`
    # (akses 5) membuat penandaan hanya berfungsi bagi pemilik usaha.
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Orang yang dapat ditandai pada pengingat.

    Peminta tidak ikut: pembuat pengingat selalu melihat pengingatnya
    sendiri, sehingga menandai diri sendiri tidak mengubah apa pun.
    """
    from repository.reminder_repository import TaggableUserRepository

    result = await TaggableUserRepository.list_for(current_user["id"])
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return {"users": result}


@router.post("/reminders")
async def create_reminder(
    body: ReminderCreate,
    current_user: Annotated[User, Depends(require("reminder", "create"))],
):
    """Buat pengingat. Untuk seluruh pengguna hanya boleh akses 4 ke atas."""
    result = await AgendaController.create(
        current_user["id"], _level(current_user), body
    )
    if "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result


@router.put("/reminders/{reminder_id}")
async def update_reminder(
    reminder_id: int,
    body: ReminderUpdate,
    current_user: Annotated[User, Depends(require("reminder", "update"))],
):
    """Ubah pengingat. Hanya pembuatnya, berapa pun levelnya."""
    result = await AgendaController.update(
        current_user["id"], _level(current_user), reminder_id, body
    )
    if "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result


@router.delete("/reminders/{reminder_id}")
async def delete_reminder(
    reminder_id: int,
    current_user: Annotated[User, Depends(require("reminder", "delete"))],
):
    """Hapus pengingat. Hanya pembuatnya, berapa pun levelnya."""
    result = await AgendaController.delete(current_user["id"], reminder_id)
    if "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result
