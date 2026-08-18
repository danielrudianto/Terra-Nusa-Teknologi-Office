"""
Tender pengadaan.

Sebelum membeli barang atau memesan jasa, procurement menyebarkan permintaan
penawaran ke beberapa pemasok, lalu mencatat balasan yang masuk. Yang dipilih
dicatat beserta alasannya; purchase order tetap dibuat terpisah.

Empat tabel, dan pemisahannya disengaja:

  tenders            permintaannya — apa yang dicari, syarat pembayarannya
  tender_items       daftar barang atau pekerjaan yang diminta
  tender_quotes      satu balasan dari satu pemasok
  tender_quote_items harga per baris pada satu balasan

`tender_quote_items` terpisah dari `tender_items` karena TIDAK setiap pemasok
menawar seluruh baris. Menyimpan harganya pada baris permintaan memaksa satu
harga per baris, dan itu justru yang hendak dibandingkan.
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

tenders_table = Table(
    "tenders",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # Nomor urut tender; dipakai menyusun sebutannya pada dokumen dan pesan.
    Column("number", Integer, nullable=True, index=True),
    Column("name", String(255), nullable=False),
    Column("date", Date, nullable=False),
    # `barang` atau `jasa`.
    #
    # Menentukan bentuk barisnya: barang diambil dari master item dengan
    # satuan dan volume; jasa ditulis bebas sebagai uraian pekerjaan.
    Column("tenderType", String(20), nullable=False),
    Column("projectName", String(255), nullable=False),
    Column("description", Text, nullable=True),
    # Syarat yang diminta AKN, bukan yang ditawarkan pemasok.
    #
    # Disebut di permintaannya supaya seluruh penawaran dapat dibandingkan
    # dengan dasar yang sama; pemasok yang mengajukan syarat berbeda dicatat
    # pada balasannya sendiri.
    Column("paymentTerm", String(20), nullable=True),
    Column("creditTerm", Integer, nullable=True),
    # Ketentuan lain: garansi, masa berlaku penawaran, syarat pengiriman.
    Column("requirements", Text, nullable=True),
    # Batas waktu penawaran masuk.
    Column("dueDate", Date, nullable=True),
    # `draft` | `berjalan` | `selesai` | `batal`
    Column("status", String(20), nullable=False, server_default="draft"),
    # Pemenang; kosong selama belum diputuskan.
    Column("winnerQuoteID", Integer, nullable=True),
    # Mengapa yang itu yang dipilih.
    #
    # Bukan selalu yang termurah: waktu kirim, garansi, dan riwayat pemasok
    # ikut menentukan. Tanpa alasan tertulis, keputusannya tidak dapat
    # ditinjau siapa pun setelah orangnya berganti.
    Column("winnerReason", Text, nullable=True),
    Column("decidedAt", DateTime, nullable=True),
    Column("decidedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("createdAt", DateTime, default=dt.now, nullable=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedAt", DateTime, nullable=True),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("isDelete", Boolean, nullable=False, server_default="0"),
    Column("deletedAt", DateTime, nullable=True),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
)

tender_items_table = Table(
    "tender_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tenderID", Integer, ForeignKey("tenders.id"), nullable=False),
    # Barang dari katalog; kosong pada tender jasa.
    Column("itemID", Integer, ForeignKey("master_item.id"), nullable=True),
    # Nama disalin, tidak hanya dirujuk lewat `itemID`.
    #
    # Permintaan penawaran adalah dokumen yang sudah disebar; namanya harus
    # tetap seperti saat disebarkan, walaupun katalognya kemudian berubah.
    Column("name", String(255), nullable=False),
    Column("specification", Text, nullable=True),
    Column("quantity", DECIMAL(15, 2), nullable=True),
    Column("unit", String(50), nullable=True),
    Column("sortOrder", Integer, nullable=False, server_default="0"),
)

tender_quotes_table = Table(
    "tender_quotes",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tenderID", Integer, ForeignKey("tenders.id"), nullable=False),
    Column("supplierID", Integer, ForeignKey("suppliers.id"), nullable=False),
    # Syarat yang DITAWARKAN pemasok; kerap berbeda dari yang diminta.
    Column("paymentTerm", String(20), nullable=True),
    Column("creditTerm", Integer, nullable=True),
    # Garansi, waktu kirim, dan ketentuan lain dari pemasok.
    Column("notes", Text, nullable=True),
    # Kapan balasannya masuk; dicatat manual karena datangnya lewat WhatsApp.
    Column("quotedAt", Date, nullable=True),
    Column("createdAt", DateTime, default=dt.now, nullable=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedAt", DateTime, nullable=True),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("isDelete", Boolean, nullable=False, server_default="0"),
    Column("deletedAt", DateTime, nullable=True),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
)

tender_quote_items_table = Table(
    "tender_quote_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("quoteID", Integer, ForeignKey("tender_quotes.id"), nullable=False),
    Column(
        "tenderItemID", Integer, ForeignKey("tender_items.id"), nullable=False
    ),
    # Harga satuan yang ditawarkan.
    #
    # NULL berarti pemasok TIDAK menawar baris itu — berbeda dari nol, yang
    # berarti digratiskan. Perbedaannya menentukan: yang tidak menawar tidak
    # boleh dihitung sebagai penawaran termurah.
    Column("price", DECIMAL(15, 2), nullable=True),
    # Catatan per baris: merek yang ditawarkan, spesifikasi pengganti.
    Column("notes", Text, nullable=True),
)
