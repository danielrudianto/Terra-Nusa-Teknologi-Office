from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
)

from utils.database import metadata

"""
Departemen yang menjadi wilayah kerja seorang pengguna.

Dibuat sebagai tabel tersendiri, bukan satu kolom pada `users`, karena satu
orang lazim menangani lebih dari satu wilayah — HRD yang juga mengurus
sebagian pembukuan, misalnya. Satu kolom memaksa memilih salah satu, dan yang
tidak terpilih akan diakali lewat izin khusus satu per satu.

Level dan departemen menjawab pertanyaan yang berbeda:

    level      -> sejauh apa: hanya membaca, boleh menghapus, boleh menyetujui
    departemen -> wilayah mana: modul apa saja yang menjadi urusannya

Keduanya harus terpenuhi. Level 1 procurement dan level 1 accounting sama
seniornya, tetapi daftar modulnya berbeda — dan itu tidak dapat dinyatakan
oleh satu angka saja.
"""

user_departments_table = Table(
    "user_departments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("userID", Integer, ForeignKey("users.id"), nullable=False, index=True),
    Column("department", String(50), nullable=False),
    Column("createdAt", DateTime(), nullable=False, default=datetime.now),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=True),
    # Satu pengguna tidak perlu tercatat dua kali pada departemen yang sama;
    # pengulangan hanya membuat penelusuran membingungkan.
    UniqueConstraint("userID", "department", name="uq_user_department"),
)
