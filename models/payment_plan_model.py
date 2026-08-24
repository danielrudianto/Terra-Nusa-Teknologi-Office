"""
Rencana pengeluaran.

Kalender sudah menampilkan pembayaran yang SUDAH terjadi. Yang belum ada
adalah yang AKAN terjadi — dan itu justru yang menentukan apakah kasnya cukup.

Bukan pengingat: pengingat menandai sesuatu yang harus dikerjakan, rencana
pengeluaran menyebut uang yang akan keluar. Keduanya muncul di kalender,
tetapi hanya yang kedua ikut dihitung pada posisi kas.

Sengaja TIDAK terhubung ke dokumen mana pun. Rencana dibuat sebelum
dokumennya ada — itu gunanya. Menuntut nomor purchase order lebih dulu
membuat rencana hanya dapat dicatat setelah tidak lagi diperlukan.
"""

from datetime import datetime as dt

from sqlalchemy import (
    Boolean,
    Column,
    DECIMAL,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)

from utils.database import metadata

payment_plans_table = Table(
    "payment_plans",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # `keluar` atau `masuk`.
    #
    # Satu tabel untuk keduanya, bukan dua tabel: bidangnya persis sama, dan
    # yang dilihat orang justru SELISIHNYA — memisahkannya berarti setiap
    # perhitungan posisi kas harus menggabungkan dua sumber lebih dulu.
    Column("planType", String(10), nullable=False, server_default="keluar"),
    Column("date", Date, nullable=False, index=True),
    Column("amount", DECIMAL(15, 2), nullable=False),
    Column("description", String(255), nullable=False),
    # Untuk apa: `material`, `subkon`, `gaji`, `operasional`, `pajak`, `lain`.
    #
    # Dipakai mengelompokkan pada ringkasan bulanan; tanpa itu daftarnya hanya
    # deretan angka yang tidak menjelaskan ke mana kasnya pergi.
    Column("category", String(30), nullable=True),
    # Proyek yang menanggung; kosong berarti beban kantor pusat.
    Column("projectName", String(255), nullable=True, index=True),
    # Rekening yang direncanakan dipakai; kosong berarti belum ditentukan.
    Column(
        "bankAccountID", Integer, ForeignKey("bank_accounts.id"), nullable=True
    ),
    Column("notes", Text, nullable=True),
    # `rencana` | `terpakai` | `batal`
    #
    # `terpakai` ditandai manual ketika pembayarannya benar-benar dilakukan.
    # TIDAK dihubungkan otomatis ke pembayaran: satu rencana kerap terpecah
    # menjadi beberapa pembayaran, dan menebak pasangannya menghasilkan
    # kecocokan yang tampak meyakinkan tetapi keliru.
    Column("status", String(20), nullable=False, server_default="rencana"),
    Column("createdAt", DateTime, default=dt.now, nullable=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedAt", DateTime, nullable=True),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("isDelete", Boolean, nullable=False, server_default="0"),
    Column("deletedAt", DateTime, nullable=True),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
)
