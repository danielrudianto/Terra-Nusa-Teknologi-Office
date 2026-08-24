"""
Ujian rekrutmen: bank soal.

Seluruh rute di berkas ini dijaga modul `hr_recruitment`, yang termasuk
`MODUL_WILAYAH_MUTLAK` — hanya divisi HRD dan pemilik. Isinya data pribadi
orang yang bahkan belum menjadi karyawan, dan jawaban yang menentukan
diterima atau tidaknya.
"""

import json
from typing import Annotated, Any, Dict, Optional

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from controllers.hr_recruitment_controller import HrRecruitmentController
from schemas.hr_recruitment_schema import (
    PelamarBatch,
    SoalCreate,
    SoalUpdate,
)
from utils.auth_utils import User
from utils.errors import error_detail
from utils.login_guard import cek_terkunci, catat_gagal
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
    # `str`, bukan `int`.
    #
    # Layar mengirim `?testID=` ketika penyaringnya kosong, dan teks kosong
    # bukan `None` bagi FastAPI: ia mencoba mengubahnya menjadi angka, gagal,
    # lalu menolak seluruh permintaan dengan 422 — sebelum satu baris pun
    # dibaca. Diterima sebagai teks lalu diubah sendiri di bawah.
    testID: Optional[str] = Query(None, description="Saring per paket ujian"),
    keyword: Optional[str] = Query(None, description="Cari di soal & catatan"),
):
    """Bank soal, disaring paket ujian dan kata pencarian."""
    try:
        test_id = int(testID) if testID not in (None, "") else None
    except ValueError:
        # Nilai yang tidak berupa angka diperlakukan sebagai tanpa penyaring,
        # bukan sebagai galat: yang mengetiknya di alamat tidak sedang
        # menyerang, dan menolak permintaannya tidak menolong siapa pun.
        test_id = None

    return _periksa(
        await HrRecruitmentController.daftar_soal(
            test_id, (keyword or "").strip() or None
        )
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


# ---------------------------------------------------------------------------
# Pelamar
# ---------------------------------------------------------------------------


@router.get("/candidates")
async def daftar_pelamar(
    user: Annotated[User, Depends(require("hr_recruitment", "read"))],
    testID: Optional[str] = Query(None, description="Saring per paket ujian"),
    status: Optional[str] = Query(None, description="baru | selesai | ..."),
):
    """Pelamar beserta paket ujian dan keadaan pengerjaannya."""
    try:
        test_id = int(testID) if testID not in (None, "") else None
    except ValueError:
        test_id = None

    return _periksa(
        await HrRecruitmentController.daftar_pelamar(
            test_id, (status or "").strip() or None
        )
    )


@router.post("/candidates")
async def daftarkan_pelamar(
    payload: PelamarBatch,
    user: Annotated[User, Depends(require("hr_recruitment", "create"))],
):
    """
    Daftarkan beberapa pelamar sekaligus dan terbitkan tokennya.

    Yang diminta hanya nama dan jenis kelamin; sisanya diisi pelamar sendiri
    lewat tautan.
    """
    return _periksa(
        await HrRecruitmentController.daftarkan_pelamar(
            payload.testID,
            [o.model_dump() for o in payload.orang],
            user["id"],
            payload.berlakuHari or 7,
        )
    )


# ---------------------------------------------------------------------------
# Ujian — TANPA masuk
#
# Yang menandai pesertanya adalah tokennya sendiri. Pelamar bukan karyawan dan
# tidak punya akun; membuatkan akun untuk satu kali ujian menambah kata sandi
# yang akan lupa lebih dulu daripada dipakai.
#
# Karena tanpa penjaga izin, rute di sini hanya boleh menyentuh data milik
# pelamar yang tokennya dibawa — tidak ada parameter yang menyebut pelamar
# lain.
# ---------------------------------------------------------------------------


@router.get("/exam/{token}")
async def periksa_token_ujian(token: str, request: Request):
    """
    Keterangan ujian untuk halaman peserta: nama, paket, durasi, jumlah soal.

    Soalnya sendiri BELUM dikirim di sini — itu baru setelah pesertanya
    memulai, karena membacanya lebih dulu berarti ia dapat menyiapkan jawaban
    tanpa timer berjalan.
    """
    # Batasi percobaan per alamat IP.
    #
    # Tokennya 256 bit dan tidak mungkin ditebak, tetapi pencobaan berulang
    # tetap membebani: setiap tebakan menjalankan dua kueri, dan rute ini
    # terbuka — yang membanjirinya tidak perlu akun sama sekali.
    ip = request.client.host if request.client else "?"
    if cek_terkunci(f"exam:{ip}", ip) > 0:
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan. Coba lagi beberapa saat.",
        )

    hasil = await HrRecruitmentController.pelamar_dari_token(token)
    if hasil is None:
        catat_gagal(f"exam:{ip}", ip)
        raise HTTPException(
            status_code=404, detail="Token tidak berlaku atau sudah kedaluwarsa."
        )
    return hasil


class JawabanUjian(BaseModel):
    """
    Jawaban yang sedang dikerjakan.

    Kunci berupa id soal sebagai teks; nilainya jawaban esai. Panjangnya
    dibatasi pada rutenya — muatan tanpa batas pada rute TERBUKA berarti satu
    permintaan dapat menulis berkilo-kilo teks ke basis data.
    """

    answers: Dict[str, Any] = {}


def _batasi_muatan(payload: "JawabanUjian") -> None:
    """
    Batas ukuran jawaban.

    256 KB jauh melampaui ujian terpanjang: tujuh puluh lima soal esai
    sekalipun hanya belasan kilobyte. Rute ini terbuka tanpa masuk, sehingga
    muatan tanpa batas hanya ditulis ke basis data sampai penuh.
    """
    if len(json.dumps(payload.answers or {})) > 256 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Jawaban terlalu panjang. Ringkas jawaban Anda.",
        )


def _jaga_laju(request: Request) -> str:
    """Batasi percobaan per alamat IP; kembalikan alamatnya."""
    ip = request.client.host if request.client else "?"
    if cek_terkunci(f"exam:{ip}", ip) > 0:
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan. Coba lagi beberapa saat.",
        )
    return ip


@router.post("/exam/{token}/mulai")
async def mulai_ujian(token: str, request: Request):
    """
    Mulai mengerjakan; mengembalikan soal dan sisa waktunya.

    Soal BARU dikirim di sini, bukan saat token diperiksa — membacanya lebih
    dulu berarti peserta dapat menyiapkan jawaban tanpa timer berjalan.

    Waktu mulai dicatat server. Memanggil ulang tidak menambah waktu:
    `startedAt` yang sudah ada tidak ditimpa.
    """
    ip = _jaga_laju(request)

    hasil = await HrRecruitmentController.mulai_ujian(token)
    if hasil is None:
        catat_gagal(f"exam:{ip}", ip)
        raise HTTPException(
            status_code=404,
            detail="Token tidak berlaku atau sudah kedaluwarsa.",
        )
    return _periksa(hasil)


@router.put("/exam/{token}/jawaban")
async def simpan_jawaban_ujian(
    token: str, payload: JawabanUjian, request: Request
):
    """
    Simpan jawaban yang sedang dikerjakan.

    Dipanggil berkala oleh layar. Koneksi di rumah pelamar kerap putus, dan
    kehilangan satu jam pengerjaan karena satu kali putus adalah kegagalan
    yang tidak dapat diperbaiki sesudahnya.
    """
    _batasi_muatan(payload)
    ip = _jaga_laju(request)

    hasil = await HrRecruitmentController.simpan_jawaban(token, payload.answers)
    if hasil is None:
        catat_gagal(f"exam:{ip}", ip)
        raise HTTPException(
            status_code=404,
            detail="Token tidak berlaku atau sudah kedaluwarsa.",
        )
    return _periksa(hasil)


@router.post("/exam/{token}/kirim")
async def kirim_ujian(token: str, payload: JawabanUjian, request: Request):
    """
    Kirim jawaban akhir; setelah ini tidak dapat disunting lagi.

    Jawaban terakhir ikut disimpan lebih dulu — yang menekan Kirim kerap baru
    saja mengetik sesuatu.
    """
    _batasi_muatan(payload)
    ip = _jaga_laju(request)

    hasil = await HrRecruitmentController.kirim_ujian(token, payload.answers)
    if hasil is None:
        catat_gagal(f"exam:{ip}", ip)
        raise HTTPException(
            status_code=404,
            detail="Token tidak berlaku atau sudah kedaluwarsa.",
        )
    return _periksa(hasil)
