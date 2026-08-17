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
    UniqueConstraint,
    Text,
)
from utils.database import metadata
from datetime import datetime as dt

"""
Induk proyek.

Sebelum tabel ini ada, "proyek" hanya berupa teks bebas `projectName` pada
purchases, purchase_drafts, purchase_orders, reimbursements, dan
sales_invoices. Akibatnya dua hal:

  * Nilai kontrak tidak tersimpan di mana pun, sehingga margin proyek tidak
    dapat dihitung.
  * Salah ketik menciptakan proyek baru tanpa ada yang tahu — "MICZ" dan
    "MICz" terhitung sebagai dua proyek berbeda pada setiap laporan.

Penyambungan ke tabel-tabel itu dilakukan lewat `code`, BUKAN lewat foreign
key. Data lama sudah terlanjur memuat kode yang tidak seragam; memasang
foreign key sekarang akan menggagalkan migrasi. Kolom teksnya dibiarkan apa
adanya sampai datanya bersih, baru sesudah itu masukannya diganti menjadi
pemilih dan tautannya dieratkan.
"""
projects_table = Table(
    "projects",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # Kode yang dipakai di seluruh dokumen (4-5 karakter, mis. "MICZ").
    # Disimpan huruf besar agar pencocokan tidak bergantung pada cara ketik.
    Column("code", String(20), nullable=False),
    Column("name", String(255), nullable=False),
    # Alamat lokasi proyek.
    #
    # Dipakai mengisi alamat pengiriman pada purchase order Franco — barang
    # dikirim ke lokasi proyeknya, dan mengetiknya ulang pada setiap PO
    # berarti menyalin dari catatan lain yang cepat atau lambat berbeda.
    #
    # `TEXT`, bukan `VARCHAR`: alamat proyek kerap beberapa baris — nama
    # lokasi, jalan, kota, patokan — dan batas panjang membuatnya terpotong
    # justru pada bagian yang menolong pengemudi menemukannya.
    Column("address", Text, nullable=True),
    Column("clientID", Integer, nullable=True),
    Column("startDate", Date(), nullable=True),
    Column("endDate", Date(), nullable=True),
    # Sengaja boolean, bukan enum teks.
    #
    # Nilai teks membuka kemungkinan nilai ngawur masuk dari luar layar, dan
    # tetap menuntut kunci terjemahan tersendiri. Boolean tidak punya keadaan
    # tak sah, dan di layar cukup diterjemahkan sebagai dua label.
    #
    # Tiga keadaan proyek dinyatakan oleh dua penanda:
    #
    #     isActive=1, isCancelled=0  -> berjalan
    #     isActive=0, isCancelled=0  -> selesai
    #     isActive=0, isCancelled=1  -> batal
    #
    # Kombinasi isActive=1 & isCancelled=1 tidak punya arti dan dijaga di
    # controller: menandai batal selalu ikut mematikan `isActive`, dan
    # mengaktifkan kembali selalu ikut membatalkan penanda batal.
    #
    # Proyek batal SENGAJA tidak memakai `isDelete`. Biaya yang terlanjur
    # dikeluarkan atasnya tetap tercatat di purchases dan reimbursements;
    # kalau induknya ikut terhapus, biaya itu menjadi yatim — terhitung di
    # total perusahaan tetapi tidak ada proyeknya. `isDelete` tetap untuk
    # kekeliruan input, bukan untuk pekerjaan yang benar-benar dibatalkan.
    Column("isActive", Boolean, nullable=False, default=True),
    Column("isCancelled", Boolean, nullable=False, default=False),
    Column("createdAt", DateTime(), nullable=False, default=dt.now),
    Column("createdBy", Integer, nullable=False),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("updatedBy", Integer, nullable=True, default=None),
    Column("isDelete", Boolean, nullable=False, default=False),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("deletedBy", Integer, nullable=True, default=None),
    # Kode proyek harus unik. Tanpa ini, dua baris berkode sama membuat
    # penyambungan dokumen menjadi ambigu dan laporannya berlipat.
    UniqueConstraint("code", name="uq_projects_code"),
)

"""
Nilai kontrak, dipecah per dokumen.

Nilai kontrak TIDAK disimpan sebagai satu kolom pada `projects`. Adendum
adalah hal biasa di pekerjaan konstruksi, dan satu kolom yang ditimpa setiap
kali nilainya berubah akan menghapus riwayatnya. Pada tahun audit,
"mengapa nilai kontraknya berbeda dari SPK awal" adalah pertanyaan yang
harus bisa dijawab dengan dokumen, bukan ingatan.

Nilai kontrak berjalan = jumlah baris di sini yang belum dihapus.

`value` boleh negatif: adendum pengurangan lingkup kerja memang mengurangi
nilai kontrak, dan mencatatnya sebagai baris negatif membuat jejaknya utuh.
"""
project_contracts_table = Table(
    "project_contracts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "projectID",
        Integer,
        ForeignKey("projects.id"),
        nullable=False,
    ),
    # Nomor SPK, kontrak, atau adendum.
    Column("documentNumber", String(100), nullable=False),
    # spk | adendum
    Column("documentType", String(20), nullable=False, default="spk"),
    # Nilai dipecah seperti dokumen aslinya, bukan disimpan sebagai satu
    # angka. Yang dipakai menghitung margin adalah DPP: PPN titipan negara
    # dan bukan pendapatan, PPh potongan pembayaran dan bukan pengurang
    # nilai pekerjaan.
    Column("dpp", Numeric(20, 2), nullable=False),
    # Persen, 0-100.
    Column("ppn", Numeric(6, 2), nullable=False, default=0),
    Column("pphCode", String(20), nullable=True),
    Column("pphTaxObject", String(255), nullable=True),
    Column("pphPercentage", Numeric(6, 2), nullable=True),
    #
    # TIDAK ada kolom `value`.
    #
    # Nominal dokumen selalu sama dengan `dpp + dpp * ppn / 100`, dan tarif
    # PPN-nya sudah tersimpan di baris ini — jadi angkanya tidak pernah bisa
    # berubah arti. Menyimpannya berarti dua tempat harus selalu sepakat,
    # dan cepat atau lambat salah satunya diperbarui tanpa yang lain.
    #
    # Nilai itu tetap dikeluarkan di respons API, dihitung saat dibaca.
    Column("date", Date(), nullable=False),
    Column("description", String(500), nullable=True),
    Column("createdAt", DateTime(), nullable=False, default=dt.now),
    Column("createdBy", Integer, nullable=False),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("updatedBy", Integer, nullable=True, default=None),
    Column("isDelete", Boolean, nullable=False, default=False),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("deletedBy", Integer, nullable=True, default=None),
)
