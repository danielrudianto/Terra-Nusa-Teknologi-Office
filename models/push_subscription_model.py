from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
    func,
)
from utils.database import metadata
from datetime import datetime as dt

"""
Langganan Web Push per perangkat.

Satu pengguna dapat masuk dari beberapa perangkat (ponsel, tablet), dan tiap
perangkat memberi satu `endpoint` unik dari layanan push peramban. Karena itu
kuncinya `endpoint`, bukan pengguna: memberi tahu berarti mengirim ke SELURUH
perangkat pengguna yang masih berlangganan.

Langganan bisa MATI tanpa kabar (peramban mencabut izin, aplikasi dihapus).
Layanan push menjawab 404/410 untuk yang mati; pengirimnya menghapus baris itu
saat itu juga — lihat `utils/webpush.py`.
"""

push_subscriptions_table = Table(
    "push_subscriptions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("userID", Integer, ForeignKey("users.id"), nullable=False),
    # URL unik pemberi push milik perangkat ini.
    Column("endpoint", Text, nullable=False),
    # Kunci enkripsi muatan (RFC 8291), dari langganan peramban.
    Column("p256dh", String(255), nullable=False),
    Column("auth", String(255), nullable=False),
    # Untuk menandai perangkat pada daftar, sekadar keterangan.
    Column("userAgent", String(255), nullable=True),
    Column(
        "createdAt",
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=dt.now,
    ),
    # Endpoint unik: memasang ulang di perangkat yang sama memperbarui, bukan
    # menggandakan. TEXT butuh panjang prefix pada indeks MySQL, jadi unik-nya
    # dinyatakan sebagai Index (bukan UniqueConstraint) dengan `mysql_length`.
    Index(
        "uq_push_endpoint",
        "endpoint",
        unique=True,
        mysql_length={"endpoint": 255},
    ),
    Index("ix_push_user", "userID"),
)
