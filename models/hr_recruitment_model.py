"""
Ujian rekrutmen.

Pelamar mengerjakan soal esai lewat tautan bertoken, tanpa akun. Jawabannya
dinilai orang, bukan dicocokkan otomatis — soalnya menuntut penjelasan, bukan
pilihan.

Dipindahkan dari sistem HR lama yang menyimpan soalnya sebagai berkas JSON di
dalam kode: menambah satu soal di sana menuntut deploy ulang seluruh aplikasi.
"""

from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Text,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
)

from utils.database import metadata


hr_tests_table = Table(
    "hr_tests",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(150), nullable=False),
    Column("description", String(500), nullable=True),
    # Durasi pengerjaan dalam menit.
    #
    # Disimpan sebagai angka, bukan waktu selesai: waktu selesai baru dapat
    # dihitung setelah pelamarnya mulai, dan sebagian tidak pernah mulai.
    Column("durationMinutes", Integer, nullable=False, server_default="90"),
    Column("isActive", Boolean(), nullable=False, server_default="1"),
    Column("isDelete", Boolean(), nullable=False, server_default="0"),
    Column("createdAt", DateTime(), nullable=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedAt", DateTime(), nullable=True),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
)


hr_questions_table = Table(
    "hr_questions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("testID", Integer, ForeignKey("hr_tests.id"), nullable=False),
    # Urutan tampil.
    #
    # Soal yang dihapus tidak menggeser nomor yang lain: jawaban menunjuk ke
    # `id`, bukan ke urutannya.
    Column("sortOrder", Integer, nullable=False, server_default="0"),
    Column("question", Text, nullable=False),
    # Catatan tambahan, mis. standar yang harus dipakai menjawab.
    Column("notes", String(500), nullable=True),
    # Lampiran berupa HTML — tabel berat besi, gambar potongan.
    #
    # Disimpan sebagai teks, bukan berkas: isinya menyatu dengan soalnya, dan
    # memisahkannya berarti satu permintaan tambahan untuk setiap soal.
    Column("attachment", Text, nullable=True),
    Column("category", String(30), nullable=False, server_default="civil"),
    Column("maxScore", Integer, nullable=False, server_default="5"),
    # Apakah soal ini menerima unggahan berkas.
    #
    # Hanya soal gambar yang memerlukannya; membuka unggahan pada seluruh soal
    # mengundang jawaban dikirim sebagai foto tulisan tangan, yang tidak dapat
    # dibaca ulang saat dinilai.
    Column("allowsUpload", Boolean(), nullable=False, server_default="0"),
    Column("isDelete", Boolean(), nullable=False, server_default="0"),
    Column("createdAt", DateTime(), nullable=False),
)


hr_candidates_table = Table(
    "hr_candidates",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("testID", Integer, ForeignKey("hr_tests.id"), nullable=False),
    Column("name", String(150), nullable=False),

    # L / P.
    #
    # Ditanyakan di muka bersama namanya, bukan diisi pelamar: yang menyusun
    # jadwal wawancara memerlukannya sebelum pelamarnya sempat membuka
    # tautan, dan sebagian tidak pernah membukanya sama sekali.
    Column("gender", String(1), nullable=True),

    Column("nickName", String(50), nullable=True),
    Column("dateOfBirth", Date(), nullable=True),
    Column("address", String(255), nullable=True),
    Column("city", String(100), nullable=True),
    Column("phoneNumber", String(30), nullable=True),
    # Surel BOLEH kosong.
    #
    # Pelamar didaftarkan hanya dengan nama dan jenis kelamin; sisanya diisi
    # sendiri lewat tautan. Mewajibkan surel di sini berarti yang mendaftarkan
    # harus mengumpulkannya lebih dulu — dan itu justru pekerjaan yang hendak
    # dihilangkan.
    Column("email", String(150), nullable=True),
    # Token acak, bukan urutan: nomor berurutan dapat ditebak, dan yang
    # menerima tautannya sendiri tinggal mengubah satu angka untuk membuka
    # lembar jawaban pelamar lain.
    Column("token", String(64), nullable=False, unique=True),
    Column("expiresAt", DateTime(), nullable=False),
    # Waktu pelamar MULAI mengerjakan; dari sinilah durasi dihitung.
    #
    # Kosong berarti belum pernah dibuka, dan itu berbeda dari "membuka lalu
    # tidak menjawab".
    Column("startedAt", DateTime(), nullable=True),
    Column("submittedAt", DateTime(), nullable=True),
    # baru | mengerjakan | selesai | diterima | ditolak
    #
    # Berkas unggahan dihapus ketika status berpindah ke `diterima` atau
    # `ditolak` — setelah diputuskan, isinya tidak diperlukan lagi.
    Column("status", String(20), nullable=False, server_default="baru"),
    Column("decidedAt", DateTime(), nullable=True),
    Column("decidedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("decisionNote", String(500), nullable=True),
    Column("isDelete", Boolean(), nullable=False, server_default="0"),
    Column("createdAt", DateTime(), nullable=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
)


hr_answers_table = Table(
    "hr_answers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "candidateID", Integer, ForeignKey("hr_candidates.id"), nullable=False
    ),
    Column(
        "questionID", Integer, ForeignKey("hr_questions.id"), nullable=False
    ),
    Column("answer", Text, nullable=True),
    # Nilai yang diberikan pemeriksa; kosong berarti belum dinilai.
    #
    # Dibedakan dari nol: nol adalah keputusan bahwa jawabannya salah, dan
    # keduanya tidak boleh tertukar saat menghitung yang belum diperiksa.
    Column("score", Integer, nullable=True),
    Column("checkedAt", DateTime(), nullable=True),
    Column("checkedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("checkerNote", String(500), nullable=True),
    Column("updatedAt", DateTime(), nullable=True),
)


hr_answer_files_table = Table(
    "hr_answer_files",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("answerID", Integer, ForeignKey("hr_answers.id"), nullable=False),
    Column("originalName", String(255), nullable=False),
    Column("sizeBytes", Integer, nullable=False),
    Column("contentType", String(100), nullable=True),
    # Jalur berkas di disk, bukan isinya.
    #
    # Gambar teknik hasil foto berukuran megabyte; menyimpannya di basis data
    # membuat setiap cadangan membawa seluruhnya.
    Column("storedPath", String(500), nullable=False),
    # Berkasnya sudah dihapus dari disk; BARISNYA TETAP ADA.
    #
    # Setelah keputusan diambil, isi berkasnya tidak diperlukan lagi — tetapi
    # pertanyaan "dia dulu mengunggah apa" masih dapat dijawab dengan nama dan
    # ukurannya.
    Column("isPurged", Boolean(), nullable=False, server_default="0"),
    Column("purgedAt", DateTime(), nullable=True),
    Column("createdAt", DateTime(), nullable=False),
)
