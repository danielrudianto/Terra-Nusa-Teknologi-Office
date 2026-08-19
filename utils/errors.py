"""
Kode galat aplikasi.

Server menyebut PENYEBAB galat lewat kode, bukan lewat kalimat. Kalimatnya
disusun di layar dari berkas terjemahan, sehingga bahasanya mengikuti pilihan
penggunanya — dan mengubah susunan kalimat tidak lagi berarti menyentuh
backend.

Sebelumnya kalimat Inggris dikirim apa adanya dan diterjemahkan di layar
dengan mencocokkan teksnya. Cara itu rapuh: satu kata yang berubah di sini
membuat terjemahannya luput tanpa ada yang menyadarinya, dan yang muncul di
layar kembali berbahasa Inggris.

Bentuk yang dikirim:

    {
      "detail": {
        "code": "SALARY_SLIP_EXISTS",
        "message": "Salary slip already exists ..."   # cadangan, untuk log
      }
    }

`message` tetap disertakan agar galat tetap terbaca pada log dan pada
klien lama yang belum mengenal kode.
"""

from typing import Any, Dict, Optional


class ErrorCode:
    """
    Daftar kode yang dikenali layar.

    Setiap kode di sini harus punya pasangannya pada `serverError.<KODE>` di
    berkas terjemahan. Kode tanpa pasangan akan tampil sebagai pesan umum.
    """

    # ---- umum ----
    NOT_FOUND = "NOT_FOUND"
    INTERNAL = "INTERNAL"
    FORBIDDEN = "FORBIDDEN"
    VALIDATION = "VALIDATION"

    # ---- sesi & kata sandi ----
    SESSION_EXPIRED = "SESSION_EXPIRED"
    CURRENT_PASSWORD_INVALID = "CURRENT_PASSWORD_INVALID"
    PASSWORD_UNSET = "PASSWORD_UNSET"
    SAME_PASSWORD = "SAME_PASSWORD"
    TOO_MANY_ATTEMPTS = "TOO_MANY_ATTEMPTS"

    # ---- slip gaji ----
    SALARY_SLIP_EXISTS = "SALARY_SLIP_EXISTS"

    # ---- pembayaran ----
    PAYMENT_NOT_FOUND = "PAYMENT_NOT_FOUND"
    PAYMENT_LOCKED = "PAYMENT_LOCKED"
    SELF_APPROVAL_FORBIDDEN = "SELF_APPROVAL_FORBIDDEN"

    # ---- proyek ----
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    PROJECT_CODE_IN_USE = "PROJECT_CODE_IN_USE"
    CONTRACT_NOT_FOUND = "CONTRACT_NOT_FOUND"

    # ---- pengingat ----
    REMINDER_NOT_FOUND = "REMINDER_NOT_FOUND"
    REMINDER_NOT_OWNER = "REMINDER_NOT_OWNER"
    REMINDER_SHARED_FORBIDDEN = "REMINDER_SHARED_FORBIDDEN"

    # ---- purchase order ----
    #
    # Kode TERSENDIRI, bukan `FORBIDDEN` biasa.
    #
    # `FORBIDDEN` diterjemahkan menjadi "Anda tidak memiliki akses untuk
    # tindakan ini" — kalimat yang benar tetapi tidak menyebut apa pun yang
    # dapat ditindaklanjuti. Yang membacanya perlu tahu bahwa dokumen ini
    # hanya dapat diubah PEMBUATNYA, sehingga ia tahu harus menghubungi siapa
    # alih-alih meminta izinnya dinaikkan.
    PO_EDIT_FORBIDDEN = "PO_EDIT_FORBIDDEN"

    # ---- data induk ----
    BANK_ACCOUNT_EXISTS = "BANK_ACCOUNT_EXISTS"
    EMPLOYEE_DELETED = "EMPLOYEE_DELETED"
    BLACKLIST_REASON_REQUIRED = "BLACKLIST_REASON_REQUIRED"
    DRAFT_ALREADY_CONVERTED = "DRAFT_ALREADY_CONVERTED"


def app_error(
    code: str,
    message: str,
    status: int = 400,
    **konteks: Any,
) -> Dict[str, Any]:
    """
    Susun galat berkode.

    Bentuk balikannya tetap memuat `error` agar seluruh pemeriksaan
    `if "error" in result` yang sudah tersebar tetap bekerja tanpa diubah.

    Nilai pada `konteks` diteruskan ke layar dan dapat dipakai sebagai
    parameter terjemahan — misalnya jumlah dokumen pada pesan "kode dipakai
    pada {{count}} dokumen".
    """
    hasil: Dict[str, Any] = {
        "error": message,
        "code": code,
        "status": status,
    }
    if konteks:
        hasil["context"] = konteks
    return hasil


def error_detail(result: Dict[str, Any]) -> Any:
    """
    Ubah galat controller menjadi isi `detail` pada HTTPException.
    
    Galat berkode dikirim sebagai objek; galat lama yang belum berkode tetap
    dikirim sebagai teks, sehingga peralihannya dapat dilakukan bertahap
    tanpa satu pun layar berhenti bekerja.
    """
    code: Optional[str] = result.get("code")
    if not code:
        return result.get("error", "Internal server error.")

    detail: Dict[str, Any] = {
        "code": code,
        "message": result.get("error", ""),
    }
    if result.get("context"):
        detail["context"] = result["context"]
    return detail


def internal_error() -> Dict[str, Any]:
    """
    Galat tak terduga, tanpa membocorkan sebabnya kepada klien.

    Pesan asli pengecualian kerap memuat nama tabel, nama kolom, dan potongan
    SQL. Mengirimkannya ke layar memberi peta sistem kepada siapa pun yang
    membuka Network tab — dan tidak menolong pengguna sama sekali, karena
    kalimatnya bukan bahasa yang ia mengerti.

    Jejak lengkapnya tetap dicatat `log_error` di tempat kejadiannya; yang
    berubah hanya apa yang keluar dari server.
    """
    return app_error(
        ErrorCode.INTERNAL,
        "Terjadi kesalahan pada sistem. Silakan coba lagi.",
        500,
    )
