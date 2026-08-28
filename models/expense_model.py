from utils.database import metadata
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey

expenses_table = Table(
    "expenses",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("invoiceName", String(100), nullable=False),
    Column("receiptName", String(100), nullable=False),
    # Nomor faktur pajak, sama seperti pada `purchases`.
    #
    # Rekap PPN punya kolom "No. Faktur Pajak"; tanpa kolom ini baris dari
    # beban selalu kosong di situ, dan faktur pajaknya tidak dapat dilacak
    # kembali ke dokumen sumbernya saat dicocokkan.
    Column("taxInvoiceName", String(100), nullable=True),
    Column("opponentID", Integer, ForeignKey("expense_opponents.id"), nullable=True),
    Column("date", Date(), nullable=False),
    Column("dueDate", Date(), nullable=True),
    Column("purchaseType", String(100), nullable=False),
    # MASA yang DITANGGUNG beban ini — hari PERTAMA periodenya.
    #
    # Untuk beban berkala yang tanggal BAYARnya kerap berbeda dari periode yang
    # ditanggung: setoran PPN/PPh, iuran BPJS, premi asuransi, SPT Tahunan.
    # Contoh: PPN masa Mei baru disetor Juni — `date` = tanggal setor (Juni),
    # `masaPajak` = 1 Mei. Untuk yang tahunan (SPT Tahunan) dipakai 1 Januari
    # tahun pajaknya.
    #
    # NULL berarti IKUT `date` — dan itu MAYORITAS beban (barang, jasa, dll.
    # yang periodenya memang sama dengan tanggal dokumennya). Dengan begitu
    # baris lama tidak perlu diisi ulang, dan hanya kategori berkala yang
    # meminta pengisiannya di layar.
    Column("masaPajak", Date(), nullable=True, default=None),
    # DECIMAL(17,4) di basis data; lihat keterangan di purchase_model.
    Column("dpp", Float(), nullable=False),
    # PERSEN, bukan rupiah — sama seperti `purchases.ppn`.
    #
    # Rekap pajak menghitung nilainya dengan `ppn * dpp / 100`. Bila kolom
    # bernama sama menyimpan arti berbeda di dua tabel, rekap gabungannya
    # pasti salah di salah satunya, dan salahnya tidak kelihatan.
    #
    # Boleh nol: sebagian pemasok bukan PKP dan tidak memungut PPN.
    # DECIMAL(5,2). Dulu FLOAT sungguhan, dan 1,1% tersimpan sebagai
    # 1,1000000238 — selisih Rp 0,12 pada nominal Rp 500 juta.
    Column("ppn", Float(), nullable=False, server_default="0"),
    # DECIMAL(17,4).
    Column("pbbkb", Float(), nullable=False),
    Column("pphCode", String(100), nullable=True),
    Column("pphTaxObject", String(500), nullable=True),
    Column("pphPercentage", Float(), nullable=False),
    Column("bankName", String(100), nullable=False),
    Column("bankAccountName", String(100), nullable=False),
    Column("bankAccountNumber", String(100), nullable=False),
    Column("paymentMethod", String(100), nullable=False),
    Column("description", String(500), nullable=False),
    Column("isPaid", Boolean(), nullable=False, default=False),
    Column("isDelete", Boolean(), nullable=False, default=False),
    Column("createdAt", DateTime(), nullable=False),
    Column("updatedAt", DateTime(), nullable=True, default=None),
    Column("deletedAt", DateTime(), nullable=True, default=None),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True, default=None),
    Column("deletedBy", Integer, ForeignKey("users.id"), nullable=True, default=None),
)