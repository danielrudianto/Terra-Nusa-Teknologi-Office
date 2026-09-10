from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Numeric,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
)
from utils.database import metadata
from datetime import datetime as dt

"""
Kemajuan pekerjaan proyek, dicatat per tanggal.

Sampai sekarang laporan proyek hanya dapat menjawab satu pertanyaan: berapa
biaya yang sudah keluar dibanding nilai kontrak. Itu setengah jawaban. Biaya
60% belum tentu buruk bila pekerjaannya juga sudah 60% — dan sangat buruk bila
pekerjaannya baru 30%. Tanpa angka kemajuan, keduanya terbaca sama persis.

Tabel INI yang menyediakan setengah yang hilang, dan sengaja hanya berisi apa
yang benar-benar dicatat orang di lapangan: tanggal, persen, dan keterangan.

Beberapa keputusan yang perlu diketahui sebelum menyuntingnya:

  * Persen disimpan apa adanya, BUKAN diturunkan dari volume BAP. Volume BAP
    baru bergerak ketika BAP-nya disetujui — kerap berminggu-minggu setelah
    keadaannya berubah di lapangan — sehingga kurvanya akan mendatar justru
    pada masa yang paling perlu terlihat.

  * Angkanya BOLEH turun. Pekerjaan yang harus diulang memang mengurangi
    kemajuan, dan memaksanya naik terus akan menyembunyikan persoalan yang
    paling mahal.

  * Tidak ada indeks unik pada (projectID, date). Baris terhapus tetap
    tersimpan; indeks unik akan menolak pencatatan ulang pada tanggal yang
    sama setelah baris pertamanya dihapus. Yang menjaga tanggal ganda adalah
    controller, yang dapat membedakan baris hidup dari baris terhapus.

  * `projectID` memakai foreign key sungguhan, berbeda dari purchases dan
    kawan-kawannya yang menyambung lewat teks `projectName`. Tabel ini baru,
    jadi tidak ada data lama berkode tidak seragam yang perlu ditampung —
    persis alasan `project_contracts` juga sudah memakai foreign key.
"""
project_progress_table = Table(
    "project_progress",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "projectID",
        Integer,
        ForeignKey("projects.id"),
        nullable=False,
    ),
    # Tanggal KEADAAN yang dilaporkan, bukan tanggal pencatatannya.
    #
    # Progress kerap dicatat beberapa hari setelah opnamenya. Memakai tanggal
    # input akan menggeser seluruh kurva ke kanan, dan perbandingannya dengan
    # kurva biaya — yang memakai tanggal dokumen — menjadi tidak sejajar.
    Column("date", Date(), nullable=False),
    # Persen kemajuan kumulatif, 0-100. Bukan tambahan per periode:
    # yang dibaca orang di lapangan adalah "sudah berapa persen", dan
    # menjumlahkan tambahan-tambahan membuat satu baris yang keliru merusak
    # seluruh sisa kurvanya.
    Column("percentage", Numeric(6, 2), nullable=False),
    Column("description", String(500), nullable=True),
    Column("createdAt", DateTime(), nullable=False, default=dt.now),
    Column("createdBy", Integer, nullable=False),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("updatedBy", Integer, nullable=True, default=None),
    Column("isDelete", Boolean, nullable=False, default=False),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("deletedBy", Integer, nullable=True, default=None),
)
