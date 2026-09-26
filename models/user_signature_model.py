from sqlalchemy import (
    Table,
    Column,
    Enum,
    Float,
    Index,
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
    # Sidik 64 bit sebagai HEKSA, bukan bilangan.
    #
    # BIGINT bertanda tidak dapat menampung 64 bit tanpa tanda, dan yang
    # terjadi bukan galat — separuh sidik tersimpan sebagai angka negatif dan
    # pembandingannya diam-diam salah. Heksa juga membuat sidiknya terbaca
    # apa adanya saat menelusuri lewat SQL.
    Column("fingerprint", String(16), nullable=True),
    # Siapa yang menyetujui PERGANTIAN ini. Kosong pada tanda tangan PERTAMA:
    # yang pertama berlaku seketika, karena setiap pengguna wajib punya dan
    # menahannya berarti mengunci orang di depan pintu yang tidak dapat
    # dilewati tanpa membuatnya.
    Column("approvedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("approvedAt", DateTime(), nullable=True),
    Column("createdAt", DateTime(), default=dt.now, nullable=False),
    Column("updatedAt", DateTime(), default=None, onupdate=dt.now, nullable=True),
)


# =====================================================================
# Permintaan penggantian tanda tangan
# =====================================================================
#
# KENAPA PERGANTIAN PERLU PERSETUJUAN, SEDANGKAN YANG PERTAMA TIDAK
#
# Yang pertama tidak menimpa apa pun: sebelumnya tidak ada tanda tangan, dan
# setiap pengguna WAJIB punya. Menahannya berarti orang baru tidak dapat
# bekerja sampai ada direktur yang sempat menekan tombol.
#
# Pergantian lain perkaranya. Ia MENGGANTI stempel yang sudah menempel pada
# dokumen-dokumen yang beredar, dan dua hal buruk dapat lewat di situ:
# seseorang memasang tiruan tanda tangan orang lain, atau seseorang mengganti
# tanda tangannya sendiri lalu menyangkal dokumen lama ("itu bukan tanda
# tangan saya").
#
# TABEL INI JUGA RIWAYATNYA
#
# Setiap versi yang pernah berlaku punya barisnya di sini, termasuk yang
# pertama (tersimpan langsung sebagai `approved`). Itu yang menjawab
# penyangkalan: bukan gambar yang berlaku hari ini, melainkan urutan gambar
# beserta tanggal dan penyetujunya.
user_signature_requests_table = Table(
    "user_signature_requests",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("userID", Integer, ForeignKey("users.id"), nullable=False, index=True),
    Column("image", LargeBinary, nullable=False),
    Column("mimeType", String(40), nullable=False, default="image/png"),
    Column("width", Integer, nullable=True),
    Column("height", Integer, nullable=True),
    Column("fingerprint", String(16), nullable=True),
    Column(
        "status",
        Enum("pending", "approved", "rejected", name="user_signature_request_status"),
        nullable=False,
        server_default="pending",
        default="pending",
    ),
    # BUKTI KEMIRIPAN DIBEKUKAN DI SINI, bukan dihitung ulang saat dibaca.
    #
    # Dihitung ulang, angkanya berubah setiap kali ada orang lain mengganti
    # tanda tangannya — dan yang dibaca pemeriksa bulan depan bukan lagi
    # angka yang dipakai menyetujui.
    Column("similarity", Float, nullable=True),
    Column("similarTo", Integer, ForeignKey("users.id"), nullable=True),
    Column("note", String(255), nullable=True),
    Column("createdAt", DateTime(), default=dt.now, nullable=False),
    Column("decidedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("decidedAt", DateTime(), nullable=True),
    Column("decisionNote", String(255), nullable=True),
    Index("ix_user_signature_request_status", "status"),
)
