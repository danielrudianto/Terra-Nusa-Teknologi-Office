from sqlalchemy import (
    Table, Column, Integer, String, Text, DECIMAL, ForeignKey, text,
)
from utils.database import metadata

purchase_order_items_table = Table(
    "purchase_order_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # Barang katalog (master_item) — PO G, F, C, 5.1.1, 5.1.2, 5.1.6, 6.3
    Column("item_id", Integer, ForeignKey("master_item.id"), nullable=True),
    # Alat sewa (master_equipment) — khusus PO B (penyewaan alat kerja)
    Column("equipment_id", Integer, nullable=True),
    Column("fleet_id", Integer, nullable=True),  # references hardcoded frontend fleet list (no DB table)
    Column("task", String(100), nullable=True),
    Column("quantity", DECIMAL(12, 2), nullable=False, server_default="0.00"),
    Column("price", DECIMAL(14, 4), nullable=False, server_default="0.0000"),
    # Jumlah baris yang DITULIS, menggantikan volume kali harga.
    #
    # Harga satuan tersimpan empat desimal, dan sebagian pekerjaan tidak
    # pernah bulat pada ketelitian itu: 7.000 liter seharga Rp 300.000 berarti
    # Rp 42,857142… per liter — yang paling dekat yang dapat disimpan adalah
    # 42,8571, menghasilkan Rp 299.999,70 pada dokumen yang ditandatangani.
    # Menambah desimal tidak menyelesaikannya; pecahannya berulang tanpa habis.
    #
    # NULL berarti "hitung seperti biasa", dan itulah keadaan SELURUH baris
    # yang sudah ada — sehingga pencetakan ulangnya tidak berubah sedikit pun.
    #
    # Selisihnya DIBATASI (lihat `TOLERANSI_PEMBULATAN`): yang ditulis hanya
    # boleh membetulkan pembulatan, bukan menggantikan perkaliannya. Tanpa
    # batas itu, kolom ini menjadi pintu memasukkan angka yang tidak ada
    # hubungannya dengan volume dan harganya.
    Column("amount", DECIMAL(17, 4), nullable=True, default=None),
    Column("remarks_1", Text, nullable=True),
    Column("remarks_2", Text, nullable=True),
    Column("remarks_3", Text, nullable=True),
    Column("remarks_4", Text, nullable=True),
    # Penanggung jawab per baris. Dipakai pada SPK jasa antar berbasis
    # aplikasi: satu SPK memuat banyak pengiriman yang ditangani orang
    # berbeda, sehingga PIC tidak bisa ditaruh di tingkat kontrak.
    Column("remarks_5", Text, nullable=True),
    Column("remarks_6", Text, nullable=True),
    Column("unit", String(45), nullable=False, server_default=""),
    # Jenis baris: NULL untuk baris biasa, "mobilisasi" / "demobilisasi"
    # untuk biaya yang menempel pada baris alat di atasnya.
    #
    # KENAPA KOLOM SUNGGUHAN, bukan menumpang `remarks_` yang ketujuh:
    #
    # Sebelumnya mobilisasi memang menumpang — `remarks_4` dan `remarks_5`.
    # Akibatnya ia tidak pernah menjadi baris: yang tercetak pada SPK
    # ("Mobilisasi Crane 25T sesuai pada nomor 1") dikarang saat mencetak dan
    # tidak ada di basis data. Certificate of payment menyertifikasi per
    # `purchase_order_items.id`, sehingga mobilisasi tidak punya tempat untuk
    # menaruh volumenya — dan SPK yang sepertiga nilainya mobilisasi hanya
    # dapat disertifikasi dua pertiga, selamanya.
    #
    # Menumpangkan arti pada kolom serbaguna itulah yang melahirkan
    # persoalan ini. Mengulanginya sekali lagi berarti membuat bug berikutnya
    # sambil membetulkan yang sekarang.
    Column("itemKind", String(20), nullable=True, default=None),
    # Baris alat yang biaya ini menempel padanya.
    #
    # Menentukan DUA hal: urutan cetak (anak menyusul induknya, bukan
    # menumpuk di akhir karena `id`-nya lebih besar — lihat `URUT_BARIS`),
    # dan penggabungan kembali ke formulir saat disunting, sehingga tampilan
    # formulirnya tidak berubah sama sekali.
    #
    # ON DELETE CASCADE di basis data: baris mobilisasi tidak punya arti
    # sendiri. Alat yang dihapus harus membawa serta biaya mobilisasinya.
    Column(
        "parentItemID",
        Integer,
        ForeignKey("purchase_order_items.id"),
        nullable=True,
        default=None,
    ),
    Column("purchaseOrderID", Integer, ForeignKey("purchase_orders.id"), nullable=False),
)


# Urutan baris SPK: anak menyusul induknya.
#
# Baris mobilisasi lahir BELAKANGAN daripada seluruh baris alat — pada
# dokumen yang dipindahkan dari bentuk lama, `id`-nya jauh lebih besar.
# Diurutkan menurut `id` saja, seluruh mobilisasi menumpuk di akhir dokumen
# dan cetak ulang SPK yang sudah ditandatangani berubah susunannya.
#
# Tiga tingkat: induk mana (anak memakai `id` induknya), induk sebelum
# anaknya, lalu urutan lahir. Mobilisasi selalu disisipkan sebelum
# demobilisasi, sehingga tingkat ketiga sudah cukup memisahkan keduanya.
#
# Dipakai SETIAP kueri yang mendaftar baris SPK. Satu tempat, karena yang
# tertinggal tidak menghasilkan galat apa pun — hanya dokumen yang susunannya
# berbeda dari dokumen yang sama di layar sebelah.
URUT_BARIS = (
    "COALESCE({a}.parentItemID, {a}.id) ASC, "
    "({a}.parentItemID IS NOT NULL) ASC, "
    "{a}.id ASC"
)


def urut_baris(alias: str = "i") -> str:
    """Potongan ORDER BY untuk daftar baris SPK; lihat `URUT_BARIS`."""
    return URUT_BARIS.format(a=alias)