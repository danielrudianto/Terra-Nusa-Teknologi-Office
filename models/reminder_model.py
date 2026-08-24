from datetime import datetime as dt

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
)

from utils.database import metadata

"""
Pengingat pada agenda.

Dipakai untuk hal yang tidak punya tempat di modul lain — perpanjangan izin,
tenggat laporan, janji dengan vendor. Yang sudah punya modulnya sendiri
(pembayaran, purchase order) tidak dicatat di sini; dua tempat untuk hal yang
sama membuat orang ragu mana yang lengkap.

Siapa yang melihat ditentukan dua hal:

    isShared = True     seluruh pengguna
    reminder_targets    orang-orang yang ditandai
    keduanya kosong     hanya pembuatnya

Membuat pengingat untuk SELURUH pengguna dibatasi akses 4 ke atas — bila
terbuka untuk semua, agenda cepat penuh oleh hal yang hanya berlaku bagi
satu-dua orang, dan begitu terlalu ramai orang berhenti membacanya.
"""

# Kategori sengaja dikunci pada daftar tetap.
#
# Isian bebas menghasilkan "pajak", "Pajak", dan "PPH" untuk hal yang sama;
# setelah beberapa bulan penyaringnya tidak lagi dapat dipercaya dan orang
# berhenti memakainya.
REMINDER_CATEGORIES = (
    "Pajak",
    "Legalitas",
    "Alat",
    "Pembayaran",
    "Proyek",
    "Kepegawaian",
    "Lainnya",
)

reminders_table = Table(
    "reminders",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("title", String(150), nullable=False),
    Column("note", String(500), nullable=True),
    Column("date", Date(), nullable=False),
    Column("category", String(30), nullable=False, server_default="Lainnya"),
    # Untuk seluruh pengguna, bukan hanya yang ditandai.
    Column("isShared", Boolean(), nullable=False, server_default="0"),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("isDelete", Boolean(), nullable=False, server_default="0"),
    Column("createdAt", DateTime(), nullable=False, default=dt.now),
    Column("updatedAt", DateTime(), nullable=True),
)

reminder_targets_table = Table(
    "reminder_targets",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "reminderID",
        Integer,
        ForeignKey("reminders.id"),
        nullable=False,
    ),
    Column("userID", Integer, ForeignKey("users.id"), nullable=False),
    # Satu orang cukup ditandai sekali pada satu pengingat.
    UniqueConstraint("reminderID", "userID", name="uq_reminder_target"),
)
