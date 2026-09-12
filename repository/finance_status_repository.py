from datetime import date as d
from typing import Any, Dict

from sqlalchemy import select, func, and_

from utils.database import database
from utils.logger_utils import log_error
from models.balance_model import balance_view
from models.purchase_model import purchases_table, nilai_pembelian_sql
from models.sales_invoice_model import (
    sales_invoice_tables,
    nilai_faktur_sql,
    terbayar_faktur_sql,
)
from models.payment_outgoing_model import payments_outgoing_table
from models.payment_incoming_model import payment_incoming_table
from models.loans_model import loans_table
from utils.errors import ErrorCode, internal_error

"""
Posisi keuangan: kas, piutang usaha, utang usaha, dan pinjaman.

Yang SENGAJA tidak dihitung di sini: laba rugi dan neraca.

TerraBot belum menghitung penyusutan, pembelian aset tercatat sebagai biaya
tipe 5.1.1 alih-alih dikapitalisasi, dan biaya tenaga kerja dapat terhitung
ganda antara purchase order tipe D, beban 5.1.4, dan slip gaji. Angka laba
yang disusun di atas ketiga hal itu akan berbeda dari pembukuan resmi, dan
laporan yang bertentangan lebih merugikan daripada tidak ada laporan.

Yang dihitung di sini semuanya dapat ditelusuri ke dokumennya sendiri:
saldo rekening, faktur yang belum dibayar, dan pembelian yang belum
dibayarkan. Tidak ada asumsi akuntansi di dalamnya.
"""

# Selisih di bawah nilai ini dianggap lunas.
#
# Pembulatan pada transfer bank kerap menyisakan beda beberapa rupiah.
# Tanpa toleransi, faktur yang secara praktis sudah lunas akan menggantung
# selamanya di daftar piutang dan menutupi yang benar-benar menunggak.
TOLERANSI_LUNAS = 5


class FinanceStatusRepository:
    @staticmethod
    async def total_kas() -> float:
        """Saldo seluruh rekening perusahaan."""
        try:
            nilai = await database.fetch_val(
                select(func.sum(balance_view.c.balance)).select_from(balance_view)
            )
            return float(nilai or 0)
        except Exception as e:
            log_error(f"Error menghitung total kas: {str(e)}")
            return 0.0

    @staticmethod
    async def piutang() -> Dict[str, Any]:
        """
        Faktur penjualan yang belum lunas, dikelompokkan menurut umurnya.

        Umur dihitung dari TANGGAL FAKTUR, bukan tanggal jatuh tempo:
        `sales_invoices` tidak menyimpan jatuh tempo. Itu disebutkan pula di
        layar supaya tidak dikira tenggat yang disepakati dengan klien.
        """
        try:
            bayar = terbayar_faktur_sql()

            # Nilai tagihan DINILAI SAMA dengan yang menentukan lunas.
            #
            # Sebelumnya di sini `DPP + PPN` saja, dengan alasan PPh memotong
            # saat pembayaran dan bukan saat penagihan. Sebagai pernyataan
            # akuntansi itu dapat dipertahankan — tetapi hanya bila
            # pembayarannya juga dicatat bruto, dan ia tidak: yang dicatat
            # adalah jumlah yang masuk ke rekening, sesudah klien memotong
            # PPh dan BPJS.
            #
            # Akibatnya faktur yang sudah lunas menyisakan piutang abadi
            # sebesar PPh + BPJS: daftar faktur menyebutnya LUNAS, umur
            # piutang di layar ini masih menagihnya, dan tidak ada pembayaran
            # apa pun yang akan pernah menutupnya. Angkanya ikut ke quick
            # ratio dan modal kerja bersih.
            nilai = nilai_faktur_sql()
            sisa = nilai - func.coalesce(bayar.c.total_paid, 0)

            rows = await database.fetch_all(
                select(
                    sales_invoice_tables.c.id,
                    sales_invoice_tables.c.name,
                    sales_invoice_tables.c.date,
                    sales_invoice_tables.c.projectName,
                    sisa.label("sisa"),
                )
                .select_from(
                    sales_invoice_tables.outerjoin(
                        bayar, bayar.c.invoice_id == sales_invoice_tables.c.id
                    )
                )
                .where(
                    and_(
                        sales_invoice_tables.c.isDelete == False,  # noqa: E712
                        # Faktur yang BELUM disetujui bukan piutang.
                        #
                        # `get_monthly_ar` sudah menuntutnya sejak awal;
                        # tanpa syarat ini, draf faktur yang belum
                        # ditandatangani siapa pun ikut tampil sebagai
                        # tagihan di layar ini dan tidak di rekap bulanan —
                        # dua jawaban atas dokumen yang sama.
                        sales_invoice_tables.c.isApprove == True,  # noqa: E712
                        sisa > TOLERANSI_LUNAS,
                    )
                )
            )

            hari_ini = d.today()
            ember = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
            total = 0.0
            for r in rows:
                s = float(r["sisa"] or 0)
                total += s
                umur = (hari_ini - r["date"]).days if r["date"] else 0
                if umur <= 30:
                    ember["0-30"] += s
                elif umur <= 60:
                    ember["31-60"] += s
                elif umur <= 90:
                    ember["61-90"] += s
                else:
                    ember["90+"] += s

            return {"total": total, "umur": ember, "jumlahDokumen": len(rows)}
        except Exception as e:
            log_error(f"Error menghitung piutang: {str(e)}")
            return {"total": 0.0, "umur": {}, "jumlahDokumen": 0,
                    "error": ErrorCode.INTERNAL}

    @staticmethod
    async def utang_usaha() -> Dict[str, Any]:
        """
        Pembelian yang belum lunas, dikelompokkan menurut jatuh temponya.

        Berbeda dari piutang, `purchases` MENYIMPAN `dueDate`, sehingga
        pengelompokan di sini memakai tenggat yang sebenarnya — bukan
        perkiraan dari tanggal dokumen.
        """
        try:
            bayar = (
                select(
                    payments_outgoing_table.c.purchaseID.label("purchase_id"),
                    func.coalesce(
                        func.sum(payments_outgoing_table.c.amount), 0
                    ).label("total_paid"),
                )
                .where(
                    payments_outgoing_table.c.isDelete == False,  # noqa: E712
                    # HANYA yang sudah disetujui.
                    #
                    # Sebelumnya saringannya cuma `isDelete`, sehingga slip
                    # yang masih menunggu persetujuan sudah dianggap
                    # mengurangi utang — padahal uangnya belum keluar. Utang
                    # usahanya karena itu tampak lebih kecil daripada yang
                    # sebenarnya, dan quick ratio serta modal kerja bersih
                    # yang dihitung darinya ikut tampak lebih sehat.
                    #
                    # `belum_dibayar` dan `pinjaman` menyaring keduanya sejak
                    # awal; hanya di sini yang tertinggal.
                    payments_outgoing_table.c.isApprove == True,  # noqa: E712
                )
                .group_by(payments_outgoing_table.c.purchaseID)
                .subquery()
            )

            # PPh DIPOTONG dari nilai utangnya.
            #
            # Yang tersisa di sini adalah yang masih harus dibayarkan KEPADA
            # PEMASOK, dan PPh tidak pernah sampai ke pemasok — ia dipotong
            # lalu disetorkan ke kas negara. Tanpa memotongnya, pembelian yang
            # sudah dibayar penuh tetap menyisakan "utang" sebesar PPh-nya,
            # selamanya, dan ikut menua di ember 90+ hari.
            #
            # Suku-sukunya kini sama persis dengan `PurchaseRepository.
            # belum_dibayar` dan dengan `nilai_pembelian` yang menentukan
            # status lunas. Sebelumnya ketiganya berselisih, dan dua layar
            # menjawab berbeda atas dokumen yang sama.
            nilai = nilai_pembelian_sql()
            sisa = nilai - func.coalesce(bayar.c.total_paid, 0)

            rows = await database.fetch_all(
                select(
                    purchases_table.c.id,
                    purchases_table.c.invoiceName,
                    purchases_table.c.dueDate,
                    purchases_table.c.projectName,
                    sisa.label("sisa"),
                )
                .select_from(
                    purchases_table.outerjoin(
                        bayar, bayar.c.purchase_id == purchases_table.c.id
                    )
                )
                .where(
                    and_(
                        purchases_table.c.isDelete == False,  # noqa: E712
                        sisa > TOLERANSI_LUNAS,
                    )
                )
            )

            hari_ini = d.today()
            ember = {"lewat": 0.0, "0-30": 0.0, "31-60": 0.0, "60+": 0.0}
            total = 0.0
            for r in rows:
                s = float(r["sisa"] or 0)
                total += s
                if not r["dueDate"]:
                    # Tanpa tenggat, diperlakukan sebagai paling mendesak.
                    # Menganggapnya jauh membuat kewajiban nyata tersembunyi.
                    ember["0-30"] += s
                    continue
                selisih = (r["dueDate"] - hari_ini).days
                if selisih < 0:
                    ember["lewat"] += s
                elif selisih <= 30:
                    ember["0-30"] += s
                elif selisih <= 60:
                    ember["31-60"] += s
                else:
                    ember["60+"] += s

            return {"total": total, "tempo": ember, "jumlahDokumen": len(rows)}
        except Exception as e:
            log_error(f"Error menghitung utang usaha: {str(e)}")
            return {"total": 0.0, "tempo": {}, "jumlahDokumen": 0,
                    "error": ErrorCode.INTERNAL}

    @staticmethod
    async def pinjaman() -> Dict[str, Any]:
        """
        Sisa pinjaman ke kreditur.

        Dikeluarkan dari penyebut quick ratio karena `loans` tidak menyimpan
        tenor maupun jadwal angsuran, sehingga porsi yang jatuh tempo dalam
        setahun tidak dapat dipisahkan. Angkanya tetap dikembalikan agar
        dapat ditampilkan di samping rasionya — kewajiban yang tidak masuk
        rumus tidak boleh menjadi kewajiban yang tidak terlihat.

        Hanya pembayaran yang SUDAH DISETUJUI yang mengurangi sisa utang.
        Pengajuan yang belum disetujui belum tentu jadi; memasukkannya
        membuat utang tampak lebih kecil daripada kenyataannya.
        """
        try:
            # Angsuran pinjaman TIDAK punya tabel sendiri: ia dicatat di
            # `payments_outgoing` dengan kolom `loanID` terisi. Mencari tabel
            # tersendiri adalah kekeliruan yang mudah terjadi di sini.
            bayar = (
                select(
                    payments_outgoing_table.c.loanID.label("loan_id"),
                    func.coalesce(
                        func.sum(payments_outgoing_table.c.amount), 0
                    ).label("total_paid"),
                )
                .where(
                    and_(
                        payments_outgoing_table.c.isDelete == False,  # noqa: E712
                        payments_outgoing_table.c.isApprove == True,  # noqa: E712
                    )
                )
                .group_by(payments_outgoing_table.c.loanID)
                .subquery()
            )

            sisa = loans_table.c.debt - func.coalesce(bayar.c.total_paid, 0)
            rows = await database.fetch_all(
                select(loans_table.c.id, sisa.label("sisa"))
                .select_from(
                    loans_table.outerjoin(bayar, bayar.c.loan_id == loans_table.c.id)
                )
                .where(sisa > TOLERANSI_LUNAS)
            )

            total = sum(float(r["sisa"] or 0) for r in rows)
            return {"total": total, "jumlahPinjaman": len(rows)}
        except Exception as e:
            log_error(f"Error menghitung pinjaman: {str(e)}")
            return {"total": 0.0, "jumlahPinjaman": 0,
                    "error": ErrorCode.INTERNAL}
