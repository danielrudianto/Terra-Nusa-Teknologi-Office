from utils.database import metadata
from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Date,
    Float,
    ForeignKey,
    func,
)

purchases_table = Table(
    "purchases",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("invoiceName", String(100), nullable=False),
    Column("receiptName", String(100), nullable=False),
    Column("taxInvoiceName", String(100), nullable=True),
    Column("supplierID", Integer, nullable=False),
    Column("date", Date(), nullable=False),
    Column("dueDate", Date(), nullable=True),
    # MASA PAJAK pengkreditan PPN masukan — hari PERTAMA bulannya.
    #
    # Terpisah dari `date`, dan itu memang perlu. `date` adalah tanggal
    # dokumen pembeliannya; masa pajak adalah bulan ketika PPN masukannya
    # dikreditkan. Keduanya kerap BERBEDA: pemasok menerbitkan faktur pajak
    # bulan Juli atas invoice bulan Juni, dan yang menentukan dokumen ini
    # masuk SPT mana adalah fakturnya, bukan invoicenya.
    #
    # Sebelum kolom ini ada, laporan PPN mengelompokkan menurut `date` —
    # sehingga faktur Juli tercatat pada masa Juni, dan angkanya tidak
    # pernah cocok dengan yang benar-benar dilaporkan.
    #
    # NULL berarti IKUT `date`. Bukan sekadar kemudahan: seluruh baris lama
    # bernilai NULL, dan tanpa arti itu laporan masa-masa yang sudah lewat
    # akan berubah begitu kolomnya ditambahkan. Artinya ditegakkan di SATU
    # tempat — `masa_pajak_efektif` pada repository — bukan diulang pada
    # tiap kueri yang membacanya.
    Column("taxPeriod", Date(), nullable=True),
    Column("purchaseOrderName", String(100), nullable=False),
    Column("projectName", String(100), nullable=False),
    Column("purchaseType", String(100), nullable=False),
    Column("procurementType", String(100), nullable=False, default="goods"),
    # DECIMAL(17,4) di basis data, bukan FLOAT — `Float()` di sini warisan
    # dan sengaja dibiarkan: menggantinya membuat `databases` mengembalikan
    # `Decimal`, dan `float * Decimal` melempar TypeError di repository.
    Column("dpp", Float(), nullable=False),
    # DECIMAL(12,2). Tarif, tetap dua desimal.
    Column("ppn", Float(), nullable=False),
    # DECIMAL(17,4).
    Column("pbbkb", Float(), nullable=False),
    Column("pphCode", String(100), nullable=True),
    Column("pphTaxObject", String(500), nullable=True),
    Column("pphPercentage", Float(), nullable=False),
    # DECIMAL(14,4).
    Column("otherValue", Float(), nullable=True),
    Column("otherValueNote", String(255), nullable=True),
    Column("isInvoiceAttached", Boolean(), nullable=False),
    Column("isReceiptAttached", Boolean(), nullable=False),
    Column("isTaxInvoiceAttached", Boolean(), nullable=False),
    Column("isCopAttached", Boolean(), nullable=False),
    # Certificate of payment yang DITAGIHKAN oleh pembelian ini.
    #
    # Ini SATU-SATUNYA sumber jawaban atas "CoP ini sudah ditagihkan belum".
    # Tidak ada penanda kedua pada sisi CoP — penanda yang harus dijaga
    # sejalan dengan barisnya cepat atau lambat berselisih, dan tidak ada
    # galat yang muncul saat itu terjadi.
    #
    # Akibat langsungnya: pembelian yang DIHAPUS membuat CoP-nya terbuka
    # kembali untuk ditagihkan, tanpa satu pun langkah tambahan. Itu memang
    # yang dikehendaki — salah input dibetulkan dengan menghapus lalu membuat
    # ulang, bukan dengan menerbitkan CoP baru atas volume yang sudah
    # memakan pagu.
    #
    # NULL untuk pembelian yang tidak berasal dari CoP — dan itu mayoritas:
    # pembelian barang tidak melewati certificate of payment sama sekali.
    Column("certificateOfPaymentID", Integer(), nullable=True),
    Column("isCopyPurchaseOrderAttached", Boolean(), nullable=False),
    Column("bankName", String(100), nullable=False),
    Column("bankAccountName", String(100), nullable=False),
    Column("bankAccountNumber", String(100), nullable=False),
    Column("paymentMethod", String(100), nullable=False),
    Column("isPaid", Boolean(), nullable=False, default=False),
    Column("isDelete", Boolean(), nullable=False, default=False),
    Column("createdAt", DateTime(), nullable=False),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("lastStatus", String(100), nullable=False, default="draft"),
    Column("lastStatusDescription", String(100), nullable=True, default=None),
    Column("isInternal", Boolean(), nullable=False, default=False)
)

def nilai_pembelian_sql():
    """
    Nilai satu pembelian, sebagai ungkapan SQL.

    Pasangan dari `nilai_pembelian()` di `payment_outgoing_controller` — yang
    itu menghitung dari satu baris yang sudah dibaca, yang ini menghitung di
    dalam kueri. Suku-sukunya HARUS sama, dan sampai sekarang tidak: rumus
    yang sama ditulis ulang di empat kueri, dan dua di antaranya menyebut
    `otherValue` tanpa `COALESCE`.

    Itu bukan soal kerapian. `otherValue` boleh NULL — dan kebanyakan
    pembelian memang menyimpannya NULL, karena ongkos angkut dan bongkar muat
    hanya ada pada sebagian dokumen. Di SQL, apa pun yang ditambahkan pada
    NULL menjadi NULL; `NULL > 5` bukan benar dan bukan salah melainkan
    UNKNOWN, dan baris yang syaratnya UNKNOWN **tidak ikut terpilih**.

    Akibatnya: pembelian yang belum dibayar sepeser pun HILANG dari daftar
    "belum dibayar" dan dari rekap utang bulanan — bukan tampil dengan angka
    keliru, melainkan tidak tampil sama sekali. Tidak ada galat, tidak ada
    baris kosong, tidak ada yang menghitung selisih. Yang menagihnya hanya
    tidak pernah melihatnya lagi.

    Sementara itu penentu status lunas (`nilai_pembelian`) memakai
    `float(x or 0)` dan tetap menghitungnya utuh — sehingga dokumen yang sama
    dianggap MASIH BERUTANG oleh satu bagian sistem dan TIDAK ADA oleh bagian
    yang lain.

    PPh dipotong: yang tersisa di sini adalah yang masih harus dibayarkan
    kepada PEMASOK, dan PPh tidak pernah sampai ke pemasok.
    """
    nol = lambda kolom: func.coalesce(kolom, 0)  # noqa: E731
    return (
        purchases_table.c.dpp
        + (purchases_table.c.dpp * nol(purchases_table.c.ppn) / 100)
        + nol(purchases_table.c.pbbkb)
        + nol(purchases_table.c.otherValue)
        - (nol(purchases_table.c.pphPercentage) * purchases_table.c.dpp / 100)
    )


purchase_status_table = Table(
    "purchase_status",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("purchaseID", Integer, nullable=False),
    Column("status", String(100), nullable=False),
    Column("createdBy", Integer, nullable=False),
    Column("createdAt", DateTime(), nullable=False),
    Column("description", String(255), nullable=True),
)