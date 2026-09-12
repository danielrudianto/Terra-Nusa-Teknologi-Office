from sqlalchemy import UniqueConstraint, Table, Column, Integer, ForeignKey, Float, Date, String, Boolean, DateTime, func, select
from utils.database import metadata
from datetime import datetime as dt

sales_invoice_tables = Table(
    "sales_invoices",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False),
    Column("date", Date, nullable=False),
    Column("projectName", String(10), nullable=False),
    Column("clientID", Integer, ForeignKey("clients.id"), nullable=False),
    # DECIMAL(17,4) di basis data; lihat keterangan di purchase_model.
    Column("dpp", Float, nullable=False, default=0.0),
    Column("pphCode", String(100), nullable=True),
    Column("pphTaxObject", String(500), nullable=True),
    Column("pphPercentage", Float, nullable=False, default=0.0),
    # DECIMAL(5,2). Dulu FLOAT sungguhan; lihat expense_model.
    Column("ppn", Float, nullable=False, default=0.0),
    Column("bpjs", Float, nullable=False, default=0.0),
    Column("spkNumber", String(100), nullable=False),
    Column("taxInvoiceName", String(100), nullable=True, default=None),
    # MASA PAJAK faktur keluaran.
    #
    # Tanggal dokumen dan masa pajaknya tidak selalu sama, dan bergesernya
    # bisa ke DUA arah:
    #
    #   * MAJU — fakturnya baru terbit setelah invoicenya berjalan, sehingga
    #     masanya jatuh sesudah tanggal invoice.
    #
    #   * MUNDUR — faktur PENGGANTI. Invoice Januari yang ketahuan keliru
    #     pada Februari dibetulkan dengan dokumen bertanggal Februari,
    #     tetapi masa pajaknya TETAP Januari mengikuti faktur aslinya.
    #     Inilah bentuk yang paling sering dipakai, dan justru arah inilah
    #     yang tidak dapat diungkapkan bila masa disamakan dengan tanggal.
    #
    # NULL berarti "ikut `date`" — itu keadaan yang normal, dan sengaja
    # disimpan NULL alih-alih menyalin tanggalnya, supaya tidak ada dua
    # sumber kebenaran yang bisa berbeda diam-diam. Bacanya lewat
    # `masa_pajak_efektif()`, bukan kolom ini langsung.
    Column("taxPeriod", Date, nullable=True, default=None),
    Column("incomeTaxInvoiceName", String(100), nullable=True, default=None),
    Column("description", String(100), nullable=True),
    # Faktur dicetak terpisah dari lampirannya.
    #
    # Kolomnya sudah ada di basis data dan layar pembuatannya sudah punya
    # isian untuk ini, tetapi tidak pernah didaftarkan di model — sehingga
    # pilihan penggunanya tidak pernah tersimpan, dan tidak ada galat yang
    # muncul karenanya.
    Column('separatedInvoice', Boolean, nullable=True, default=False),
    Column("bankAccountID", Integer, ForeignKey("bank_accounts.id"), nullable=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False, default=1),
    # Bawaannya CALLABLE, bukan tanggal yang sudah dihitung.
    #
    # `default=dt.utcnow().date()` dijalankan SEKALI saat modulnya diimpor,
    # sehingga nilainya membeku pada tanggal server dinyalakan — bukan
    # tanggal fakturnya dibuat. Sebuah layanan yang hidup tiga bulan akan
    # memberi bawaan yang sama kepada seluruh faktur selama tiga bulan itu.
    #
    # Tidak pernah menggigit sampai sekarang karena `SalesInvoiceRepository.
    # create` selalu mengisi `createdAt` sendiri — dan memang harus, sebab
    # pustaka `databases` menjalankan kueri TERKOMPILASI sehingga bawaan
    # sisi-Python tidak pernah dipakai (lihat CLAUDE.md). Dibetulkan supaya
    # jebakannya tidak menunggu pemanggil berikutnya yang lupa mengisinya.
    #
    # Sekalian membuang `utcnow()` yang sudah usang: ia mengembalikan waktu
    # tanpa zona, dan Python akan menghapusnya.
    Column("createdAt", Date, nullable=False, default=lambda: dt.now().date()),
    Column("isApprove", Boolean, nullable=False, default=False),
    Column("isDelete", Boolean, nullable=False, default=False),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
    Column("updatedAt", DateTime, nullable=True, default=None),
    # Nomor faktur; dipakai pelanggan merujuk tagihan.
    UniqueConstraint("name", name="uq_sales_invoice_name"),
)


def nilai_faktur_sql():
    """
    Nilai satu faktur penjualan, sebagai ungkapan SQL.

    DPP + PPN − PPh − BPJS. Dua suku terakhir adalah POTONGAN yang dilakukan
    klien sebelum mentransfer: PPh dipotong lalu disetorkan klien ke kas
    negara atas nama AKN, BPJS dipotong dan disetorkan ke BPJS. Keduanya
    tidak pernah masuk ke rekening AKN.

    Karena itu inilah yang harus dibandingkan dengan pembayaran yang masuk —
    dan `payment_incoming.amount` memang berisi jumlah yang MASUK KE BANK:
    barisnya membawa `bankAccountID`, ikut menggerakkan saldo dan kalender
    kas, dan layar pencatatannya menyodorkan `dpp + ppn − pph` sebagai
    sasaran yang harus dilunasi.

    `piutang()` di `finance_status_repository` sebelumnya menilainya
    `DPP + PPN` saja, dengan alasan "PPh tidak mengurangi tagihan". Sebagai
    pernyataan akuntansi itu dapat dipertahankan — tetapi hanya bila
    pembayarannya juga dicatat bruto. Dicatat neto, sisanya TIDAK PERNAH
    mencapai nol: setiap faktur yang sudah lunas meninggalkan piutang abadi
    sebesar PPh + BPJS, menua sampai ember 90+ hari, dan ikut menghitung
    quick ratio serta modal kerja bersih.

    Bukan soal dua mazhab pembukuan, melainkan satu ukuran yang tidak dapat
    ditutup oleh pembayaran apa pun. Persis pola yang sudah diperbaiki pada
    `utang_usaha` pekan lalu, di sisi sebaliknya.
    """
    nol = lambda kolom: func.coalesce(kolom, 0)  # noqa: E731
    si = sales_invoice_tables.c
    return (
        si.dpp
        + (nol(si.ppn) * si.dpp) / 100
        - (nol(si.pphPercentage) * si.dpp) / 100
        - nol(si.bpjs)
    )


def terbayar_faktur_sql():
    """
    Jumlah yang sudah diterima atas satu faktur, sebagai subkueri.

    Menyaring `isDelete` — dan itu yang sebelumnya tidak dilakukan satu pun
    dari keempat subkueri yang menghitungnya. Pembayaran yang dibatalkan
    tetap dihitung sebagai penerimaan, sehingga faktur yang pembayarannya
    dibatalkan (mis. tercatat ke faktur yang keliru lalu dihapus) tetap
    terbaca lunas dan HILANG dari umur piutang maupun rekap bulanan —
    senilai penuh fakturnya, tanpa jejak.

    Repository pembayaran masuk sendiri sudah menyaringnya di setiap
    pembacaannya; hanya subkueri-subkueri inilah yang tertinggal.
    """
    from models.payment_incoming_model import payment_incoming_table

    return (
        select(
            payment_incoming_table.c.salesInvoiceID.label("invoice_id"),
            func.coalesce(func.sum(payment_incoming_table.c.amount), 0).label(
                "total_paid"
            ),
        )
        .where(payment_incoming_table.c.isDelete == False)  # noqa: E712
        .group_by(payment_incoming_table.c.salesInvoiceID)
        .subquery()
    )
