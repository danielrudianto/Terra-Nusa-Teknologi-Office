from sqlalchemy import (UniqueConstraint, 
    Float,
    text,
    func,
    Table,
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Date,
    DECIMAL,
    JSON,
    Text,
    Enum,
    ForeignKey,
    Index,
)
from utils.database import metadata
from datetime import datetime as dt
import enum


# Status enum — matches the DB enum('draft','approved','completed','cancelled')
class PurchaseOrderStatus(enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Define the purchase_orders table (aligned to production DDL)
purchase_orders_table = Table(
    "purchase_orders",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date", Date, nullable=False),
    Column("supplierID", Integer, ForeignKey("suppliers.id"), nullable=False),
    Column("name", String(255), nullable=False),
    # Nomor urut per proyek. Disimpan terpisah dari "name" supaya urutan
    # berikutnya tidak perlu diambil dengan mem-parsing teks nomor PO.
    Column("number", Integer(), nullable=True, index=True),
    Column("purchaseType", String(50), nullable=False),
    Column("templateVersion", String(50), nullable=False),
    Column("projectName", String(255), nullable=False),
    Column("dpp", DECIMAL(17, 4), nullable=False),
    Column(
        "status",
        Enum(
            "draft",
            "approved",
            "completed",
            "cancelled",
            name="purchase_order_status",
        ),
        server_default="draft",
        default="draft",
    ),
    Column("customData", JSON, nullable=True, default=None),
    Column("ppn", DECIMAL(5, 2), nullable=False, server_default="0.00", default=0.00),
    # Nilai DI LUAR dasar pajak yang tetap harus dibayarkan.
    #
    # Dipakai penutupan pertanggungan (6.4.2): premi dititipkan kepada broker
    # untuk diteruskan kepada penanggung, sehingga ia bukan penghasilan broker
    # dan tidak boleh menambah DPP — tetapi ia TETAP berpindah tangan.
    #
    # Tanpa kolom ini, layar mengirimkannya dan basis data membuangnya diam-
    # diam: daftar, tampilan, dan rekap purchase order lalu menunjukkan
    # Rp 35.000 untuk dokumen yang nilainya Rp 5.002.109.
    Column(
        "otherValue",
        DECIMAL(17, 4),
        nullable=False,
        server_default="0.0000",
        default=0,
    ),

    # Selaras dengan tabel purchases agar PO mudah disambungkan ke pembelian.
    # pphPercentage dibuat nullable: sebagian besar PO tidak memotong PPh,
    # sedangkan pada purchases kolomnya wajib terisi.
    Column("pphCode", String(100), nullable=True),
    Column("pphTaxObject", String(500), nullable=True),
    Column("pphPercentage", Float(), nullable=True),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("createdAt", DateTime, nullable=False, server_default=func.now(), default=dt.now),
    Column("isDelete", Boolean, server_default=text("0"), default=False),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True, default=None),
    Column("deletedAt", DateTime, nullable=True, default=None),
    Column("note", Text, nullable=True),
    Column("billing_requirements", JSON, nullable=False),
    Column("payment_term", String(45), nullable=False, server_default="CASH", default="CASH"),
    Column("revision", Integer, nullable=False, server_default="0", default=0),
    # ---- adendum ----
    #
    # Adendum disimpan sebagai DOKUMEN TERSENDIRI, menunjuk induknya.
    #
    # Bukan sebagai penyuntingan dokumen lama: lembar yang sudah
    # ditandatangani vendor tidak boleh berubah isinya. Bila dokumen asli
    # dapat disunting, yang dipegang vendor dan yang di sistem dapat berbeda
    # tanpa jejak — dan itu justru yang hendak dihindari dengan membuat
    # adendum.
    #
    # Isinya SELISIH, bukan pengganti. Pada `013-PO-BPBP-F` yang aslinya
    # 100 m3, adendumnya memuat 5 m3 — bukan 105. Karena itu nilai akhir
    # sebuah pekerjaan adalah induk ditambah seluruh adendumnya, dan
    # penjumlahan biasa pada laporan sudah menghasilkan angka yang benar
    # tanpa perlakuan khusus.
    Column(
        "parentPurchaseOrderID",
        Integer,
        ForeignKey("purchase_orders.id"),
        nullable=True,
    ),
    # Urutan adendum: 1, 2, dan seterusnya. NULL pada dokumen induk.
    Column("addendumNumber", Integer, nullable=True),
    Column("isApproved", Boolean, nullable=False, server_default=text("0"), default=False),
    Column("approvedBy", Integer, ForeignKey("users.id"), nullable=True, default=None),
    Column("approvedAt", DateTime, nullable=True, default=None),

    # --- tahap pemeriksaan, sebelum persetujuan ---
    #
    # Dokumen melewati DUA tangan: diperiksa dulu, baru disetujui. Pemeriksa
    # membaca isinya — harga, volume, spesifikasi; penyetuju memutuskan
    # dokumen itu boleh terbit.
    #
    # Dipisah karena keduanya menjawab pertanyaan yang berbeda, dan yang
    # menggabungkannya berarti satu orang menjawab keduanya sendirian.
    Column("isChecked", Boolean(), nullable=False, server_default="0"),
    Column("checkedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("checkedAt", DateTime(), nullable=True),
    Index("idx_supplier_date", "supplierID", "date"),
    Index("idx_type_status", "purchaseType", "status"),
    # Nomor PO yang sudah beredar.
    #
    # Nomornya disusun aplikasi dari MAX, dan dua orang yang menerbitkan
    # BERSAMAAN dapat memperoleh angka yang sama sebelum salah satunya
    # tersimpan. Dua dokumen bernomor sama tidak dapat dibedakan vendor.
    UniqueConstraint("name", name="uq_purchase_order_name"),
)