from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from repository.laba_rugi_repository import LabaRugiRepository
from repository.audit_log_repository import AuditLogRepository
from utils.auth_utils import get_current_user, User
from utils.errors import error_detail
from utils.permission import is_allowed

router = APIRouter()


@router.get("/laba-rugi")
async def laba_rugi(
    current_user: Annotated[User, Depends(get_current_user)],
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
):
    """
    Laba rugi konsolidasi (akrual) — bulan berjalan + akumulasi tahun berjalan.

    DUA JALUR, dan keduanya perlu.

    1. LEVEL 5 — pemilik usaha, apa pun divisinya. Jalur ini dipertahankan
       persis seperti semula: laba rugi menyeluruh adalah angka pemilik, dan
       pemilik belum tentu berada di divisi mana pun. Menggantungkannya pada
       izin divisi saja justru dapat menutup aksesnya sendiri.

    2. IZIN MODUL `laba_rugi` — untuk yang perlu membacanya tanpa berhak atas
       seluruh sistem. Konsultan akuntansi & pajak persisnya: ia mencocokkan
       "versi kita" dengan pembukuannya, tetapi tidak boleh memegang rekening
       bank, pinjaman, pengguna, maupun persetujuan dokumen — dan itulah yang
       ikut terbawa bila ia diberi level 5 hanya demi laporan ini.

    Ditulis sebagai DUA syarat berdampingan, bukan satu izin yang menggantikan
    level: menghapus jalur pertama membuat akses pemilik bergantung pada baris
    divisi yang mungkin belum pernah diisi untuknya.

    Batasnya ditegakkan di server, bukan sekadar disembunyikan di sidenav.

    "Versi kita" untuk dicocokkan dengan pembukuan akuntan; tiap baris dapat
    ditelusuri ke kategori dokumennya. Lihat `repository/laba_rugi_repository`.
    """
    return await _laba_rugi_terjaga(current_user, month, year, "")


async def _laba_rugi_terjaga(current_user, month: int, year: int, jenis: str):
    """
    Penjagaan akses + jejak audit + angka — SATU tempat untuk layar & PDF.

    Dipisah dari rutenya supaya rute PDF tidak menyalin syaratnya. Dua
    salinan syarat akses berarti suatu hari salah satunya dilonggarkan
    tanpa yang lain, dan laporan yang ditolak di layar tetap dapat diunduh
    utuh sebagai PDF.
    """
    level = int(current_user["authenticationLevel"] or 1)
    if level < 5 and not await is_allowed(current_user, "laba_rugi", "read"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FORBIDDEN",
                "message": (
                    "Laporan laba rugi hanya untuk pemilik usaha atau yang "
                    "diberi izin membacanya."
                ),
            },
        )

    await AuditLogRepository.catat_akses_laporan(
        "laba_rugi", f"Laba rugi {month}/{year}{jenis}"
    )

    hasil = await LabaRugiRepository.laba_rugi(month, year)
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(
            status_code=hasil.get("status", 500), detail=error_detail(hasil)
        )
    return hasil


@router.get("/laba-rugi/pdf")
async def laba_rugi_pdf(
    current_user: Annotated[User, Depends(get_current_user)],
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
):
    """
    Laporan laba rugi sebagai PDF — angka yang SAMA dengan layar.

    Bukan susunan angka kedua: datanya dari `LabaRugiRepository.laba_rugi`
    yang sama, melewati penjagaan yang sama. Yang berbeda hanya bentuknya —
    seluruh kelompok dicetak terbuka, karena kertas tidak dapat dibuka.

    Jejak auditnya ditandai "(PDF)": membaca laporan di layar dan membawa
    pulang salinannya adalah dua hal yang berbeda, dan yang memeriksa jejak
    itu kelak perlu dapat membedakannya.
    """
    from services.pdf_service import LabaRugiDocumentService

    hasil = await _laba_rugi_terjaga(current_user, month, year, " (PDF)")

    try:
        nama = current_user["name"]
    except (KeyError, TypeError):
        nama = ""

    isi = LabaRugiDocumentService.render(hasil, nama or "")
    return Response(
        content=isi,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="Laba-Rugi-{year}-{month:02d}.pdf"'
            )
        },
    )
