from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from repository.employee_form_repository import EmployeeFormRepository
from utils.auth_utils import User
from utils.errors import error_detail
from utils.logger_utils import log_error
from utils.permission import require

import os

from services.mail_service import MailService

# Alamat frontend, dipakai menyusun tautan pengisian.
#
# Dibaca dari lingkungan, bukan ditulis di kode: server klien lain akan
# memakai domain yang berbeda, dan tautan yang menunjuk ke domain AKN tidak
# akan pernah terbuka bagi mereka.
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://terrabot.alphakonstruksi.id")


def _badan_undangan(nama: str, pengundang: str, tautan: str) -> str:
    """
    Badan surel undangan.

    Menyebut pengundangnya dan masa berlakunya. Tautan tanpa asal yang jelas
    tampak seperti percobaan penipuan — dan yang berhati-hati justru tidak
    mengisinya.
    """
    return f"""<p>Halo {nama},</p>

<p>{pengundang} meminta Anda memperbarui data karyawan.
Silakan buka tautan di bawah ini dan isi datanya.</p>

<p><a href="{tautan}">{tautan}</a></p>

<p><b>Tautan ini berlaku 3 hari.</b> Setelah itu Anda perlu meminta tautan
baru kepada bagian HRD.</p>

<p>Terima kasih.</p>
"""


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



# CATATAN URUTAN — jangan memindahkan blok di bawah ke belakang.
#
# FastAPI mencocokkan rute BERURUTAN, dan menjalankan dependensi sebuah rute
# sebelum memeriksa apakah nilai jalurnya sesuai tipe. `/isi/{token}` cocok
# dengan pola `/{employee_id}/{version_id}` — dua segmen — sehingga bila rute
# itu terdaftar lebih dulu, penjaga izinnya berjalan dan menolak dengan 401
# sebelum sempat diketahui bahwa "isi" bukan angka.
#
# Yang membuka tautan karena itu dialihkan ke halaman masuk, padahal ia
# memang tidak punya akun.

# ---------------------------------------------------------------------------
# Pengisian mandiri oleh karyawan
#
# Rute di bawah ini TIDAK memerlukan masuk. Yang menandai penggunanya adalah
# tokennya sendiri — dan itu disengaja: karyawan lapangan tidak punya akun,
# dan membuatkan akun untuk pengisian setahun sekali menambah kata sandi yang
# akan lupa lebih dulu daripada dipakai.
#
# Karena tanpa penjaga izin, setiap rute di sini hanya boleh menyentuh data
# milik karyawan yang tokennya dibawa — tidak ada parameter yang menyebut
# karyawan lain.
# ---------------------------------------------------------------------------


@router.get("/isi/{token}")
async def baca_untuk_pengisian(token: str):
    """
    Pertanyaan dan jawaban yang sudah ada, untuk halaman pengisian mandiri.
    """
    undangan = await EmployeeFormRepository.undangan_dari_token(token)
    if undangan is None:
        # Token tidak dikenal, sudah dicabut, dan sudah kedaluwarsa dijawab
        # SAMA. Membedakannya memberi tahu penebak bahwa tokennya pernah ada.
        raise HTTPException(status_code=404, detail="Tautan tidak berlaku.")

    # Versi AKTIF yang dipakai, sama seperti pengisian lewat aplikasi.
    #
    # Undangan mencatat versi yang berlaku saat diterbitkan, tetapi masa
    # berlakunya hanya tiga hari — jauh lebih pendek daripada jarak antar
    # versi formulir, sehingga keduanya praktis selalu sama. Memakai versi
    # aktif menjaga satu jalur pengisian, bukan dua yang dapat menyimpang.
    versi = await EmployeeFormRepository.active_version()
    if not versi or "error" in versi:
        raise HTTPException(status_code=404, detail="Formulir tidak ditemukan.")

    jawaban = await EmployeeFormRepository.get_submission(
        undangan["employeeID"], undangan["versionID"]
    )

    return {
        "employeeName": undangan["employeeName"],
        "expiresAt": undangan["expiresAt"],
        "pengundang": undangan.get("pengundang"),
        "version": versi,
        # Jawaban sebelumnya ikut dikirim.
        #
        # Sebagian besar isian tidak berubah dari tahun lalu; meminta
        # mengetiknya ulang membuat orang mengisi asal supaya cepat selesai.
        "answers": (jawaban or {}).get("answers") if jawaban else None,
    }


@router.put("/isi/{token}")
async def simpan_pengisian_mandiri(token: str, payload: Jawaban):
    """
    Simpan jawaban dari halaman pengisian mandiri.

    `employeeID` diambil dari TOKEN, bukan dari muatan — muatan dapat disusun
    sendiri oleh siapa pun, dan menerima employeeID dari sana berarti satu
    orang dapat menimpa data seluruh karyawan.
    """
    undangan = await EmployeeFormRepository.undangan_dari_token(token)
    if undangan is None:
        raise HTTPException(status_code=404, detail="Tautan tidak berlaku.")

    # Versi AKTIF, sama dengan yang dibaca halaman pengisian.
    #
    # Menyimpan ke versi yang tercatat pada undangan sementara halaman
    # menampilkan versi aktif membuat jawabannya tersimpan pada formulir yang
    # BERBEDA dari yang dijawab — dan itu tidak menimbulkan galat apa pun,
    # hanya riwayat yang menunjuk pertanyaan yang salah.
    versi_aktif = await EmployeeFormRepository.active_version()
    version_id = (versi_aktif or {}).get("id") or undangan["versionID"]

    hasil = await EmployeeFormRepository.save_submission(
        undangan["employeeID"],
        version_id,
        payload.answers,
        # Pelaku dicatat sebagai penerbit undangan; karyawan tidak punya akun,
        # sehingga jejaknya menunjuk ke yang mengundangnya.
        undangan.get("createdBy") or 0,
    )
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(
            status_code=hasil.get("status", 500), detail=error_detail(hasil)
        )

    await EmployeeFormRepository.tandai_terpakai(undangan["id"])
    return hasil

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


@router.post("/{employee_id}/undang")
async def terbitkan_undangan(
    employee_id: int,
    user: Annotated[User, Depends(require("employee_form", "update"))],
):
    """
    Terbitkan tautan pengisian dan kirimkan ke surel karyawan.

    Dijaga izin yang sama dengan mengisi formulir atas nama orang lain —
    menerbitkan tautan berarti memberi seseorang kuasa mengubah datanya
    sendiri, dan itu setara.
    """
    versi = await EmployeeFormRepository.active_version()
    if not versi or "error" in versi:
        raise HTTPException(status_code=404, detail="Formulir aktif tidak ada.")

    hasil = await EmployeeFormRepository.buat_undangan(
        employee_id, versi["id"], user["id"]
    )
    if "error" in hasil:
        raise HTTPException(
            status_code=hasil.get("status", 500), detail=error_detail(hasil)
        )

    # Kirim tautannya ke surel karyawan.
    #
    # Kegagalan pengiriman TIDAK menggagalkan penerbitan: tokennya sudah
    # dibuat dan sah, dan yang menerbitkannya tetap dapat menyalin tautannya
    # untuk dikirim lewat jalan lain. Menggagalkan seluruh permintaan berarti
    # menerbitkan token kedua untuk orang yang sama.
    hasil["emailTerkirim"] = False
    karyawan = await EmployeeFormRepository.karyawan_ringkas(employee_id)
    alamat = (karyawan or {}).get("email")

    if alamat:
        # Nama pengundang dibungkus try.
        #
        # Objek dari `require()` adalah Record, bukan dict: ia tidak punya
        # `.get()`, dan kolom yang tidak ada melempar galat dengan jejak
        # tumpukan yang tidak menyebut sebabnya. Sudah menjatuhkan satu
        # endpoint sebelumnya.
        try:
            nama_pengundang = user["name"]
        except (KeyError, TypeError):
            nama_pengundang = "TerraBot"

        tautan = f"{FRONTEND_URL.rstrip('/')}/isi/{hasil['token']}"
        try:
            MailService.send_email(
                alamat,
                "Pembaruan data karyawan",
                _badan_undangan(
                    (karyawan or {}).get("name") or "",
                    nama_pengundang,
                    tautan,
                ),
                None,
            )
            hasil["emailTerkirim"] = True
        except Exception as e:
            log_error(f"Gagal mengirim undangan ke {alamat}: {str(e)}")

    return hasil

