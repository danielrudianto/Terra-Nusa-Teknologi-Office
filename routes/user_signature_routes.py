from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from controllers.user_signature_controller import UserSignatureController
from schemas.user_signature_schema import UserSignatureKeputusan, UserSignatureSave
from utils.errors import error_detail
from utils.permission import require

router = APIRouter()


def _id(current_user) -> int:
    """
    Id peminta.

    `current_user` adalah baris basis data, bukan dict biasa — sebagian
    tempat membacanya dengan kunci, sebagian dengan atribut. Diambil di satu
    tempat supaya tidak ada rute yang kebetulan memakai bentuk yang salah dan
    menyimpan tanda tangan ke id `None`.
    """
    try:
        return int(current_user["id"])
    except Exception:
        return int(getattr(current_user, "id"))


@router.get("/status")
async def status(
    current_user: Annotated[dict, Depends(require("user_signature", "read"))],
):
    """Sudah punya tanda tangan? Dipanggil layar pada setiap login."""
    return await UserSignatureController.status(_id(current_user))


@router.get("/me")
async def milik_sendiri(
    current_user: Annotated[dict, Depends(require("user_signature", "read"))],
):
    """
    Tanda tangan MILIK PEMINTA.

    SENGAJA tidak ada `/{user_id}`. Gambar tanda tangan adalah stempel:
    sekali sampai di peramban seseorang, ia dapat ditempelkan ke dokumen apa
    pun di luar sistem ini. Pencapan pada dokumen resmi dikerjakan server
    saat persetujuan — tidak pernah dengan mengirimkan gambarnya ke layar
    orang lain.
    """
    hasil = await UserSignatureController.milik_sendiri(_id(current_user))
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(status_code=hasil["status"], detail=error_detail(hasil))
    return hasil


@router.put("/me")
async def simpan(
    muatan: UserSignatureSave,
    current_user: Annotated[dict, Depends(require("user_signature", "update"))],
):
    """Simpan atau ganti tanda tangan SENDIRI. Tidak ada jalan menulis milik orang lain."""
    hasil = await UserSignatureController.simpan(_id(current_user), muatan.image)
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(status_code=hasil["status"], detail=error_detail(hasil))
    return hasil


@router.get("/riwayat")
async def riwayat(
    current_user: Annotated[dict, Depends(require("user_signature", "read"))],
):
    """Riwayat versi tanda tangan SENDIRI — tanpa gambarnya."""
    return await UserSignatureController.riwayat(_id(current_user))


# ---------------------------------------------------------------------------
# Persetujuan — level 5 (matriks: user_signature:approve = 5)
# ---------------------------------------------------------------------------


@router.get("/permintaan")
async def daftar_permintaan(
    current_user: Annotated[dict, Depends(require("user_signature", "approve"))],
):
    """
    Antrean pergantian tanda tangan, BESERTA gambarnya.

    Satu-satunya jalan keluar bagi gambar tanda tangan orang lain, dan itu
    tidak terhindarkan: yang menyetujui harus melihat apa yang disetujuinya.
    Dijaga `approve`, yang pada matriks bernilai 5.
    """
    hasil = await UserSignatureController.daftar_tertunda()
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(status_code=hasil["status"], detail=error_detail(hasil))
    return hasil


@router.post("/permintaan/{request_id}/setujui")
async def setujui(
    request_id: int,
    keputusan: UserSignatureKeputusan,
    current_user: Annotated[dict, Depends(require("user_signature", "approve"))],
):
    hasil = await UserSignatureController.putuskan(
        request_id, True, _id(current_user), keputusan.note
    )
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(status_code=hasil["status"], detail=error_detail(hasil))
    return hasil


@router.post("/permintaan/{request_id}/tolak")
async def tolak(
    request_id: int,
    keputusan: UserSignatureKeputusan,
    current_user: Annotated[dict, Depends(require("user_signature", "approve"))],
):
    hasil = await UserSignatureController.putuskan(
        request_id, False, _id(current_user), keputusan.note
    )
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(status_code=hasil["status"], detail=error_detail(hasil))
    return hasil
