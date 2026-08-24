from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from repository.employee_form_repository import EmployeeFormRepository
from utils.auth_utils import User
from utils.errors import error_detail
from utils.logger_utils import log_error
from utils.login_guard import cek_terkunci, catat_gagal
from utils.permission import require

import json
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

    Ditulis sebagai TABEL, bukan div ber-flexbox: klien surel — terutama
    Outlook — mengabaikan sebagian besar CSS tata letak modern, dan yang
    tampak rapi di peramban berantakan di kotak masuk.

    Gayanya disisipkan sebaris (`style="..."`) karena banyak klien membuang
    blok `<style>` di kepala dokumen.

    Menyebut pengundangnya dan masa berlakunya. Tautan tanpa asal yang jelas
    tampak seperti percobaan penipuan — dan yang berhati-hati justru tidak
    mengisinya.
    """
    return f"""<!DOCTYPE html>
<html lang="id">
<body style="margin:0;padding:0;background:#f4f5f7;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background:#f4f5f7;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:520px;background:#ffffff;border-radius:12px;
                      border:1px solid #e3e6eb;overflow:hidden;
                      font-family:Arial,Helvetica,sans-serif;">

          <tr>
            <td style="padding:24px 28px 0;">
              <div style="font-size:12px;font-weight:bold;letter-spacing:2px;
                          color:#1a56db;">TERRABOT</div>
              <div style="font-size:11px;color:#6b7280;padding-top:2px;">
                PT ALPHA KONSTRUKSI NUSANTARA
              </div>
            </td>
          </tr>

          <tr>
            <td style="padding:20px 28px 0;">
              <div style="font-size:18px;font-weight:bold;color:#16181d;">
                Pembaruan Data Karyawan
              </div>
            </td>
          </tr>

          <tr>
            <td style="padding:16px 28px 0;font-size:14px;line-height:1.65;
                       color:#374151;">
              <p style="margin:0 0 12px;">Kepada Yth.<br>
                <strong>{nama}</strong></p>

              <p style="margin:0 0 12px;">
                Bersama surel ini, <strong>{pengundang}</strong> meminta
                Anda memperbarui data karyawan pada sistem TerraBot.
              </p>

              <p style="margin:0 0 20px;">
                Silakan tekan tombol di bawah ini untuk membuka formulirnya.
                Anda tidak perlu masuk; tautan tersebut sudah mengenali Anda.
              </p>
            </td>
          </tr>

          <tr>
            <td align="center" style="padding:0 28px 20px;">
              <!--
                Tombol dibuat dari tabel, bukan tag <button>: klien surel
                tidak menjalankan apa pun, dan hanya tautan yang bekerja.
              -->
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background:#1a56db;border-radius:8px;">
                    <a href="{tautan}"
                       style="display:inline-block;padding:12px 28px;
                              font-size:14px;font-weight:bold;color:#ffffff;
                              text-decoration:none;">Buka Formulir</a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <tr>
            <td style="padding:0 28px 20px;">
              <div style="background:#fff8e6;border:1px solid #f0c14b;
                          border-radius:8px;padding:12px 14px;font-size:13px;
                          line-height:1.6;color:#7a5c00;">
                <strong>Tautan ini berlaku 3 hari.</strong><br>
                Setelah itu Anda perlu meminta tautan baru kepada bagian HRD.
              </div>
            </td>
          </tr>

          <tr>
            <td style="padding:0 28px 24px;font-size:12px;line-height:1.6;
                       color:#6b7280;">
              <p style="margin:0 0 8px;">
                Bila tombol di atas tidak berfungsi, salin alamat berikut ke
                peramban Anda:
              </p>
              <p style="margin:0;word-break:break-all;">
                <a href="{tautan}" style="color:#1a56db;">{tautan}</a>
              </p>
            </td>
          </tr>

          <tr>
            <td style="padding:16px 28px;background:#f9fafb;
                       border-top:1px solid #e3e6eb;font-size:11px;
                       line-height:1.6;color:#9aa1b1;">
              Surel ini dikirim otomatis oleh sistem TerraBot. Mohon tidak
              membalas surel ini. Bila Anda merasa tidak seharusnya menerima
              surel ini, abaikan saja — tautannya akan kedaluwarsa dengan
              sendirinya.
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
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
async def baca_untuk_pengisian(token: str, request: Request):
    """
    Pertanyaan dan jawaban yang sudah ada, untuk halaman pengisian mandiri.
    """
    # Batasi percobaan per alamat IP.
    #
    # Tokennya 256 bit dan tidak mungkin ditebak, tetapi PENCOBAAN BERULANG
    # tetap membebani: setiap tebakan menjalankan satu kueri, dan rute ini
    # terbuka — yang membanjirinya tidak perlu akun sama sekali.
    #
    # Memakai penjaga yang sama dengan halaman masuk; ia sudah terbukti dan
    # menyimpan hitungannya di Redis, bukan di memori proses.
    ip = request.client.host if request.client else "?"
    sisa = cek_terkunci(f"isi:{ip}", ip)
    if sisa > 0:
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan. Coba lagi beberapa saat.",
        )

    undangan = await EmployeeFormRepository.undangan_dari_token(token)
    if undangan is None:
        # Tebakan yang meleset DICATAT; yang benar tidak.
        catat_gagal(f"isi:{ip}", ip)
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
        # Definisi pertanyaan DISARING, bukan diteruskan mentah.
        #
        # `active_version()` mengembalikan seluruh kolom barisnya — termasuk
        # `createdBy`, `updatedBy`, dan `createdAt`. Rute ini terbuka tanpa
        # masuk, dan siapa pun yang memegang tautan dapat membacanya; id
        # pengguna internal tidak ada gunanya bagi yang mengisi formulir, dan
        # setiap keterangan yang tidak diperlukan adalah keterangan yang
        # tidak perlu diberikan.
        "version": {
            "id": versi.get("id"),
            "title": versi.get("title"),
            "description": versi.get("description"),
            "fields": versi.get("fields"),
        },
        # Jawaban sebelumnya ikut dikirim.
        #
        # Sebagian besar isian tidak berubah dari tahun lalu; meminta
        # mengetiknya ulang membuat orang mengisi asal supaya cepat selesai.
        "answers": (jawaban or {}).get("answers") if jawaban else None,
    }


@router.put("/isi/{token}")
async def simpan_pengisian_mandiri(
    token: str, payload: Jawaban, request: Request
):
    """
    Simpan jawaban dari halaman pengisian mandiri.

    `employeeID` diambil dari TOKEN, bukan dari muatan — muatan dapat disusun
    sendiri oleh siapa pun, dan menerima employeeID dari sana berarti satu
    orang dapat menimpa data seluruh karyawan.
    """
    # Batasi UKURAN muatan.
    #
    # `Dict[str, Any]` menerima apa pun, tanpa batas — dan rute ini terbuka.
    # Muatan berukuran ratusan megabyte tidak menimbulkan galat; ia hanya
    # ditulis ke kolom JSON sampai basis datanya penuh.
    #
    # 256 KB jauh melampaui formulir terpanjang yang mungkin: seluruh
    # pertanyaannya sendiri hanya belasan kilobyte.
    BATAS_MUATAN = 256 * 1024
    if len(json.dumps(payload.answers)) > BATAS_MUATAN:
        raise HTTPException(
            status_code=413,
            detail="Isian terlalu besar. Ringkas jawaban Anda.",
        )

    ip = request.client.host if request.client else "?"
    if cek_terkunci(f"isi:{ip}", ip) > 0:
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan. Coba lagi beberapa saat.",
        )

    undangan = await EmployeeFormRepository.undangan_dari_token(token)
    if undangan is None:
        catat_gagal(f"isi:{ip}", ip)
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

