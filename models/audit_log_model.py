from sqlalchemy import (
    func,
    Table,
    Column,
    Integer,
    String,
    DateTime,
    JSON,
    ForeignKey,
    Index,
)
from utils.database import metadata
from datetime import datetime as dt

"""
Jejak audit: mencatat siapa mengubah apa dan kapan.

Tabel-tabel yang ada sudah menyimpan createdBy/updatedBy/deletedBy, tetapi
hanya keadaan terakhir — nilai sebelum perubahan hilang tertimpa. Untuk data
yang menyangkut uang (purchase order, pembayaran, gaji), justru riwayat
itulah yang dibutuhkan saat ada sengketa atau pemeriksaan.

Satu tabel dipakai untuk seluruh entitas agar penelusuran lintas modul cukup
satu kueri, dan menambah modul baru tidak perlu tabel baru.
"""

audit_logs_table = Table(
    "audit_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # Entitas yang disentuh, mis. "purchase_orders" + id barisnya.
    Column("entity", String(64), nullable=False),
    Column("entityID", Integer, nullable=False),
    # create | update | delete | approve | reject | print
    Column("action", String(32), nullable=False),
    Column("userID", Integer, ForeignKey("users.id"), nullable=True),
    # Nama disalin saat kejadian: pengguna bisa dihapus atau berganti nama,
    # sedangkan catatan audit harus tetap terbaca apa adanya.
    Column("userName", String(255), nullable=True),
    # Hanya kolom yang berubah, dalam bentuk {kolom: {"from": ..., "to": ...}}.
    Column("changes", JSON, nullable=True),
    # Keterangan bebas, mis. alasan pembatalan.
    Column("note", String(500), nullable=True),
    Column("ipAddress", String(64), nullable=True),
    Column(
        "createdAt",
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=dt.now,
    ),
    # Penelusuran paling sering: "riwayat dokumen ini" dan "aktivitas orang ini".
    Index("ix_audit_entity", "entity", "entityID"),
    Index("ix_audit_user", "userID", "createdAt"),
    Index("ix_audit_created", "createdAt"),
)