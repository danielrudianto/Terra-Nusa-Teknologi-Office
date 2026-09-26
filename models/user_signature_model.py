from sqlalchemy import (
    Table,
    Column,
    Integer,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
)

from utils.database import metadata
from datetime import datetime as dt

# Tanda tangan pengguna, sebagai GAMBAR PNG.
#
# ── Kenapa tabel sendiri, bukan kolom di `users` ────────────────────────────
#
# `users` dibaca pada SETIAP permintaan (`get_current_user`), dan hampir
# semua pembacaannya `select(users_table)` — seluruh kolom. Blob 20-40 KB di
# sana berarti puluhan kilobita ikut terbaca tiap kali seseorang mengklik apa
# pun. Tidak ada galat; aplikasinya sekadar menjadi berat, dan sebabnya nyaris
# mustahil ditebak belakangan.
#
# ── Kenapa di basis data, bukan berkas di `storage/` ────────────────────────
#
# `scripts/backup_db.sh` hanya menjalankan `mysqldump`; isi `storage/` tidak
# ikut dicadangkan. Sebagai berkas, memulihkan cadangan menghasilkan sistem
# yang utuh tetapi tanda tangan semua orang hilang — dan itu baru ketahuan
# saat ada yang hendak menyetujui dokumen.
#
# ── Kenapa PNG, bukan koordinat goresannya ──────────────────────────────────
#
# Menyimpan deret titik lebih kecil dan dapat digambar ulang pada ukuran
# berapa pun, TETAPI bentuknya lalu bergantung pada kode penggambar: satu
# perubahan pada kurvanya mengubah bentuk tanda tangan pada dokumen yang
# sudah terbit. Lembar yang sudah ditandatangani tidak boleh berubah. PNG
# membekukan apa yang orang itu setujui.
#
# ── Konsekuensi yang disengaja ──────────────────────────────────────────────
#
# Di basis data berarti ikut di SETIAP dump, dan dump berpindah-pindah
# (laptop, cadangan, staging). Tanda tangan direktur ada di dalamnya. Itu
# bukan alasan menaruhnya di tempat lain — data gaji dan nilai kontrak sudah
# di sana — tetapi dump backend karena itu naik kelas kerahasiaannya.
user_signatures_table = Table(
    "user_signatures",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # Satu tanda tangan per orang. `unique` bukan kenyamanan: tanpa itu,
    # penyimpanan yang gagal separuh meninggalkan dua baris dan yang terbaca
    # adalah "yang mana saja" — tanda tangan yang berganti-ganti sendiri
    # antar dokumen.
    Column(
        "userID",
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    ),
    # PNG mentah. MEDIUMBLOB di MySQL; SQLAlchemy memetakan LargeBinary ke
    # BLOB, jadi jenis kolomnya ditetapkan di migrasi (lihat catatan rilis).
    Column("image", LargeBinary, nullable=False),
    # Selalu "image/png" saat ini. Disimpan supaya kelak dapat menerima SVG
    # tanpa menebak isi kolomnya.
    Column("mimeType", String(40), nullable=False, default="image/png"),
    # Lebar x tinggi piksel saat disimpan — dipakai pencapan server agar
    # nisbah sisinya tidak berubah.
    Column("width", Integer, nullable=True),
    Column("height", Integer, nullable=True),
    Column("createdAt", DateTime(), default=dt.now, nullable=False),
    Column("updatedAt", DateTime(), default=None, onupdate=dt.now, nullable=True),
)
