from sqlalchemy import Table, Column, Integer, String, DECIMAL, DateTime

from utils.database import metadata

"""
Pita acuan rasio keuangan — HANYA yang diubah dari bawaannya.

Baris yang tidak ada berarti "pakai bawaan", dan bawaannya hidup di kode.
Dengan begitu tabel ini boleh kosong sama sekali tanpa membuat satu pun pita
menjadi nol, dan menghapus satu baris MENGEMBALIKAN bawaannya alih-alih
menghapus pitanya.
"""

finance_thresholds_table = Table(
    "finance_thresholds",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    #: Rasio yang diatur: quickRatio, debtToEquity, dso, dpo, ...
    Column("kode", String(50), nullable=False, unique=True),
    #: Batas bawah & atas pita. NULL berarti sisi itu tidak dibatasi —
    #: DSO misalnya tidak punya batas bawah yang bermakna.
    Column("bawah", DECIMAL(14, 4), nullable=True),
    Column("atas", DECIMAL(14, 4), nullable=True),
    Column("updatedAt", DateTime, nullable=True),
    Column("updatedBy", Integer, nullable=True),
)
