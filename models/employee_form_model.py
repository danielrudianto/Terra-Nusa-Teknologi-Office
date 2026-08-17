from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
)
from utils.database import metadata

"""
Formulir keadaan karyawan yang ditanyakan berkala.

Yang disimpan di sini hanya yang BERUBAH: susunan keluarga, alamat dan
kontak, kontak darurat, riwayat kesehatan, pelatihan baru. Data yang menempel
pada orangnya ada di `employee_profiles`.

Pertanyaannya disimpan bersama jawabannya lewat `versionID`. Itu bagian yang
paling menentukan: bila tahun depan pertanyaan "status pernikahan" diganti
menjadi "jumlah tanggungan", jawaban tahun lalu tidak boleh ikut terbaca
sebagai pertanyaan yang baru. Dengan menyimpan versinya, jawaban 2026 selalu
dibaca dengan pertanyaan 2026 — tanpa perlu menyalin apa pun.
"""

employee_form_versions_table = Table(
    "employee_form_versions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # Label periode sebagaimana dipakai orang, mis. "2026" atau "2026 S1".
    Column("period", String(50), nullable=False),
    Column("title", String(200), nullable=False),
    Column("description", String(500), nullable=True),
    # Susunan pertanyaan: daftar bagian, tiap bagian berisi daftar isian.
    # Bentuknya ditentukan aplikasi, bukan basis data — menambah jenis isian
    # baru tidak boleh memerlukan migrasi tabel.
    Column("fields", JSON, nullable=False),
    # Hanya versi aktif yang dapat diisi. Versi lama tetap ada karena
    # jawabannya menunjuk ke sini.
    Column("isActive", Boolean(), nullable=False, server_default="0"),
    Column("isDelete", Boolean(), nullable=False, server_default="0"),
    Column("createdAt", DateTime(), nullable=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedAt", DateTime(), nullable=True),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
)


employee_form_submissions_table = Table(
    "employee_form_submissions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("employeeID", Integer, ForeignKey("employees.id"), nullable=False),
    Column(
        "versionID",
        Integer,
        ForeignKey("employee_form_versions.id"),
        nullable=False,
    ),
    # Jawaban, dikunci pada `key` tiap isian di versinya.
    Column("answers", JSON, nullable=False),
    # Karyawan yang belum mengisi TIDAK punya baris di sini.
    #
    # Sengaja begitu: baris kosong untuk semua orang membuat "belum mengisi"
    # dan "sudah mengisi tetapi kosong" tidak dapat dibedakan, padahal
    # keduanya berarti hal yang berbeda saat HRD menagih.
    Column("submittedAt", DateTime(), nullable=False),
    Column("submittedBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedAt", DateTime(), nullable=True),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("isDelete", Boolean(), nullable=False, server_default="0"),
)

"""
Undangan pengisian: satu tautan sekali kirim untuk satu karyawan.

Karyawan mengisi datanya sendiri lewat tautan ini, tanpa akun dan tanpa
masuk. Tokennya yang menandai siapa dia — bukan nama atau NIK yang diketik
sendiri, yang satu huruf salah saja membuat jawabannya tidak tertaut ke
siapa pun.
"""
employee_form_invites_table = Table(
    "employee_form_invites",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("employeeID", Integer, ForeignKey("employees.id"), nullable=False),
    Column("versionID", Integer, ForeignKey("employee_form_versions.id"),
           nullable=False),

    # Token acak, bukan urutan.
    #
    # Nomor berurutan dapat ditebak: yang menerima tautannya sendiri dapat
    # mengubah satu angka dan membuka data rekannya. Panjangnya dibuat cukup
    # sehingga menebaknya tidak mungkin dalam praktik.
    Column("token", String(64), nullable=False, unique=True),

    # Batas waktu, tiga hari sejak dikirim.
    #
    # Tautan yang tidak pernah kedaluwarsa akan tersimpan di riwayat pesan
    # dan grup — dan siapa pun yang menemukannya kelak dapat membuka data
    # pribadi orang tersebut.
    Column("expiresAt", DateTime(), nullable=False),

    # Waktu pengisian TERAKHIR, bukan penanda sekali pakai.
    #
    # Orang kerap menyadari ada yang keliru setelah menekan kirim; token yang
    # langsung mati memaksanya menghubungi HRD untuk satu huruf.
    Column("usedAt", DateTime(), nullable=True),

    Column("createdAt", DateTime(), nullable=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("isDelete", Boolean(), nullable=False, server_default="0"),
)
