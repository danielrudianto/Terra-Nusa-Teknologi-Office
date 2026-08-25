"""
Certificate of Payment (CoP) — berita acara progres yang menjadi dasar
penagihan atas sebuah SPK.

BENTUKNYA

    SPK 013-SPK-MICZ-B  "sewa excavator 200 jam"
      |
      +-- CoP 001  minggu 1   40 jam
      +-- CoP 002  minggu 2   65 jam
      +-- CoP 003  minggu 3   50 jam      akumulasi 155 dari 200
                                          sisa pagu 45

Yang mengisi orang lapangan (level 1, divisi engineering). Ia mengisi VOLUME
saja; harganya tidak pernah dikirimkan kepadanya — lihat `price` di bawah.

PAGU DIJAGA PER BARIS SPK, BUKAN PER JENIS PEKERJAAN

Sebuah pekerjaan yang volumenya bertambah TIDAK diperbesar dengan menyunting
CoP atau SPK-nya, melainkan dengan ADENDUM — dan adendum di sistem ini adalah
dokumen tersendiri berisi SELISIH, dengan baris-barisnya sendiri.

Karena itu pagu dihitung per baris `purchase_order_items`, bukan per "jenis
pekerjaan" yang disatukan lintas dokumen:

  * baris induk  "excavator 200 jam @ Rp 400.000"  -> pagu 200
  * baris adendum "excavator  50 jam @ Rp 425.000" -> pagu 50, baris sendiri

Menyatukan keduanya menjadi satu pagu 250 memaksa memilih SATU harga untuk
volume yang harganya memang dua — dan yang dipilih diam-diam akan salah pada
salah satunya. Dipisah, setiap volume tertagih pada harga yang benar-benar
disepakati untuknya, dan "akumulasi tidak melebihi SPK" tetap terjaga karena
jumlah seluruh pagu baris sama dengan nilai SPK beserta adendumnya.
"""

from datetime import datetime as dt

from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    DECIMAL,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
    text,
)

from utils.database import metadata


certificate_of_payments_table = Table(
    "certificate_of_payments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # Nomor yang beredar, mis. `013-SPK-MICZ-B/CoP-002`.
    #
    # Unik seperti nomor purchase order, dan karena alasan yang sama: nomor
    # disusun aplikasi dari MAX, dan dua orang yang menerbitkan BERSAMAAN
    # dapat memperoleh angka yang sama sebelum salah satunya tersimpan.
    Column("name", String(255), nullable=False),
    # Urutan CoP DALAM SATU SPK: 1, 2, 3 ... Disimpan terpisah dari `name`
    # supaya urutan berikutnya tidak perlu diambil dengan mem-parsing teks.
    Column("number", Integer, nullable=False),
    # Urutan DOKUMEN dalam satu PROYEK — angka pertama pada nomor CoP
    # ("001-R501-VIII-2026"). Berjalan terus, tidak pernah kembali ke 1.
    #
    # SENGAJA TERPISAH dari `number` di atas, dan keduanya tidak boleh
    # ditukar-tukar:
    #
    #   `number`         = pembayaran ke berapa ATAS SPK INI. Inilah yang
    #                      tercetak sebagai "Pembayaran ke" dan yang menyusun
    #                      daftar akumulasi pada lembar CoP.
    #   `documentNumber` = urutan berkas dalam arsip PROYEK. Ia hanya nomor
    #                      surat; tidak ada hitungan uang yang bergantung
    #                      padanya.
    #
    # Satu proyek dapat memiliki sepuluh SPK, dan CoP pertama SPK kesepuluh
    # tetap pembayaran ke-1 sementara nomor dokumennya sudah 037.
    #
    # NULL berarti dokumen lama yang terbit sebelum penomoran ini berlaku.
    Column("documentNumber", Integer, nullable=True),
    # SPK yang disertifikasi. Selalu dokumen INDUK — adendum menambah pagu
    # pada rantai yang sama, bukan membuka rangkaian CoP tersendiri.
    Column(
        "purchaseOrderID",
        Integer,
        ForeignKey("purchase_orders.id"),
        nullable=False,
    ),
    Column("projectName", String(255), nullable=False),
    Column("date", Date, nullable=False),
    # Periode pekerjaan yang disertifikasi — "minggu 1" dinyatakan sebagai
    # tanggal, bukan angka minggu: minggu ke berapa berbeda-beda tafsirannya
    # antar proyek, sedangkan rentang tanggal tidak.
    Column("periodStart", Date, nullable=True),
    Column("periodEnd", Date, nullable=True),
    Column("note", Text, nullable=True),
    Column(
        "status",
        Enum(
            "draft",
            "approved",
            "cancelled",
            name="certificate_of_payment_status",
        ),
        nullable=False,
        server_default="draft",
    ),
    # ---- ringkasan nilai ----
    #
    # DISIMPAN, bukan dihitung ulang tiap kali dibaca.
    #
    # Angka-angka inilah yang diteruskan ke pembukuan, dan yang tersimpan
    # harus tetap terbaca sama di kemudian hari — sekalipun harga baris SPK
    # kelak berbeda atau barisnya berpindah. Menghitungnya ulang saat dibaca
    # membuat dokumen yang sudah disetujui dapat berubah nilainya sendiri.
    #
    # Ditulis ulang server setiap kali baris atau penyesuaiannya berubah;
    # layar TIDAK pernah mengirimkannya.
    Column(
        "grossAmount",
        DECIMAL(17, 4),
        nullable=False,
        server_default="0.0000",
    ),
    Column(
        "deductionTotal",
        DECIMAL(17, 4),
        nullable=False,
        server_default="0.0000",
    ),
    Column(
        "additionTotal",
        DECIMAL(17, 4),
        nullable=False,
        server_default="0.0000",
    ),
    # kotor - potongan + tambahan.
    #
    # Sekaligus DASAR PENGENAAN PAJAK yang diteruskan ke pembukuan: potongan
    # di sini MENGURANGI DPP, bukan sekadar mengurangi transfer.
    #
    # Alasannya uang muka. Uang muka sudah difakturkan sendiri di awal
    # beserta PPN-nya; bila CoP berikutnya tetap ber-DPP penuh, PPN atas
    # bagian uang muka terhitung DUA KALI — sekali pada faktur uang muka,
    # sekali lagi pada faktur progres.
    Column(
        "netAmount",
        DECIMAL(17, 4),
        nullable=False,
        server_default="0.0000",
    ),
    # ---- tiga lapis: dibuat -> diperiksa -> disetujui ----
    #
    # Sama seperti purchase order, dan disengaja: yang mencatat progres
    # (lapangan) bukan yang memastikan angkanya benar (engineering), dan
    # bukan pula yang memutuskan ia boleh ditagihkan.
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column(
        "createdAt",
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=dt.now,
    ),
    Column("isChecked", Boolean, nullable=False, server_default=text("0")),
    Column("checkedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("checkedAt", DateTime, nullable=True),
    Column("isApproved", Boolean, nullable=False, server_default=text("0")),
    Column("approvedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("approvedAt", DateTime, nullable=True),
    # Hapus lunak: CoP yang sudah dihapus TIDAK ikut menghitung pagu, tetapi
    # jejaknya tetap ada. Menghapus keras berarti volume yang pernah
    # disertifikasi lenyap tanpa keterangan.
    Column("isDelete", Boolean, nullable=False, server_default=text("0")),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("deletedAt", DateTime, nullable=True),
    UniqueConstraint("name", name="uq_cop_name"),
    Index("ix_cop_po", "purchaseOrderID"),
    Index("ix_cop_status", "status", "isDelete"),
)


certificate_of_payment_items_table = Table(
    "certificate_of_payment_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "certificateOfPaymentID",
        Integer,
        ForeignKey("certificate_of_payments.id"),
        nullable=False,
    ),
    # Baris SPK yang ditarik. Boleh milik dokumen induk MAUPUN adendumnya —
    # keduanya baris sah pada rantai yang sama.
    Column(
        "purchaseOrderItemID",
        Integer,
        ForeignKey("purchase_order_items.id"),
        nullable=False,
    ),
    # Satu-satunya angka yang diisi orang lapangan.
    Column("quantity", DECIMAL(12, 2), nullable=False, server_default="0.00"),
    # Harga DISALIN dari baris SPK saat CoP dibuat, bukan dikirim layar.
    #
    # Dua alasan, keduanya perlu:
    #
    #   1. Orang lapangan tidak boleh tahu harga. Bila harga datang dari
    #      layar, ia harus lebih dulu dikirimkan KE layar — dan yang sampai
    #      di peramban sudah bukan rahasia, sekalipun tidak ditampilkan.
    #
    #   2. Yang tersertifikasi harus tetap terbaca sama di kemudian hari.
    #      Salinan ini merekam harga yang berlaku saat itu.
    Column("price", DECIMAL(14, 4), nullable=False, server_default="0.0000"),
    # quantity x price pada saat CoP dibuat. Disimpan, bukan dihitung ulang,
    # dengan alasan yang sama seperti `price`.
    Column("amount", DECIMAL(17, 4), nullable=False, server_default="0.0000"),
    Column("remarks", Text, nullable=True),
    Index("ix_cop_item_cop", "certificateOfPaymentID"),
    Index("ix_cop_item_po_item", "purchaseOrderItemID"),
)


# =====================================================================
# Penyesuaian: potongan & tambahan
# =====================================================================
#
# Yang mengisinya PEMERIKSA (level 2 ke atas), bukan orang lapangan — di
# tahap inilah nilai rupiah mulai terlihat.
#
# KATEGORI BERNAMA, BUKAN LABEL BEBAS
#
# Pembukuan perlu memetakan tiap potongan ke perlakuannya sendiri. Dengan
# label bebas, "Retensi", "retensi 5%", dan "Ret." menjadi tiga hal berbeda
# yang harus dipilah tangan setiap bulan. Kategori bernama membuat pemetaan
# itu tinggal dibaca.
#
# `lain_lain` tetap disediakan — yang tidak terduga selalu ada, dan tanpa
# tempatnya orang akan menitipkannya pada kategori yang salah.
#
# TAMBAHAN TIDAK MENYENTUH PAGU SPK
#
# Ia BUKAN nilai pekerjaan, melainkan biaya di luar kontrak (penggantian
# ongkos kirim, mobilisasi tak terduga). Pekerjaan yang volumenya bertambah
# tetap wajib lewat adendum — bila tambahan boleh menampung volume, seluruh
# penjagaan pagu dapat dilewati hanya dengan menuliskannya di sini.

#: Kategori potongan.
KATEGORI_POTONGAN = (
    "uang_muka",   # amortisasi uang muka yang sudah dibayarkan di awal
    "retensi",     # ditahan sampai masa pemeliharaan berakhir
    "denda",       # keterlambatan atau mutu
    "pph",         # potongan pajak penghasilan
    "lain_lain",
)

#: Kategori tambahan.
KATEGORI_TAMBAHAN = (
    "biaya_luar_kontrak",
    "lain_lain",
)


certificate_of_payment_adjustments_table = Table(
    "certificate_of_payment_adjustments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "certificateOfPaymentID",
        Integer,
        ForeignKey("certificate_of_payments.id"),
        nullable=False,
    ),
    # 'deduction' mengurangi, 'addition' menambah.
    #
    # Dipisah dari kategorinya supaya tandanya tidak pernah bergantung pada
    # nama: `amount` SELALU positif, dan yang menentukan arah hanya kolom ini.
    # Nominal bertanda minus adalah cara paling mudah membuat laporan
    # menjumlahkan potongan sebagai tambahan tanpa ada yang menyadarinya.
    Column(
        "kind",
        Enum("deduction", "addition", name="cop_adjustment_kind"),
        nullable=False,
    ),
    Column("category", String(40), nullable=False),
    # Wajib diisi saat kategorinya `lain_lain`; ditegakkan di controller.
    Column("label", String(255), nullable=True),
    # SELALU positif — lihat catatan pada `kind`.
    Column("amount", DECIMAL(17, 4), nullable=False, server_default="0.0000"),
    Column("note", Text, nullable=True),
    Index("ix_cop_adj_cop", "certificateOfPaymentID"),
    Index("ix_cop_adj_kategori", "kind", "category"),
)
