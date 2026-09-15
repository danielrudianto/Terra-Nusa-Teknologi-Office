"""
Arus kas satu proyek: uang yang BENAR-BENAR bergerak, bukan dokumennya.

KENAPA INI BUKAN PENGULANGAN "ARUS PER MINGGU" YANG SUDAH ADA

Laporan proyek yang sudah ada menghitung dari TANGGAL DOKUMEN — tanggal
pembelian, tanggal faktur. Itu menjawab "sudah berkomitmen berapa". Ia tidak
menjawab "kapan uangnya keluar dari rekening", dan pada pekerjaan konstruksi
jarak antara keduanya berminggu-minggu sampai berbulan-bulan.

Dua proyek dengan biaya dan tagihan yang sama persis bisa sangat berbeda
kasnya: yang satu menagih di muka, yang lain menalangi enam bulan. Perbedaan
itu tidak terlihat sama sekali pada tanggal dokumen.

Karena itu modul ini membaca tabel PEMBAYARAN, bukan tabel dokumen.

TIGA HAL YANG MENENTUKAN ANGKANYA, DAN ALASANNYA

1. `isDelete` SAJA yang menyaring, bukan `isApprove`.

   Ini mengikuti kalender kas dan saldo bank, yang keduanya menghitung
   pembayaran begitu tercatat. Alasannya ada di repository pembayaran itu
   sendiri: penolakan dan pembatalan MENCABUT `isApprove` sekaligus menyetel
   `isDelete`, jadi `isDelete = 0` sudah berarti "pembayaran ini berlaku".
   Menambahkan `isApprove = 1` di sini akan membuat laporan proyek melaporkan
   kas yang berbeda dari kalender untuk uang yang sama — dan yang menemukannya
   tidak punya cara tahu mana yang benar.

2. DOKUMEN INDUKNYA ikut disaring `isDelete`.

   Pembayaran atas pembelian yang kemudian dihapus tidak boleh tetap terhitung
   sebagai kas proyek. Tanpa saringan ini, menghapus satu pembelian justru
   menaikkan biaya kas proyeknya — arah yang berlawanan dengan yang diharapkan
   siapa pun.

3. JOIN-nya MENYEBUT KOLOMNYA SENDIRI (`onclause` eksplisit).

   `payment_incoming.salesInvoiceID` dideklarasikan sebagai
   `ForeignKey("purchases.id")` di modelnya — menunjuk tabel yang SALAH.

   Akibatnya SQLAlchemy tidak mengenal satu pun hubungan antara
   `payment_incoming` dan `sales_invoices`. `join(sales_invoice_tables)` tanpa
   `onclause` karena itu GAGAL dengan `NoForeignKeysError`, bukan menyambung
   diam-diam ke tabel yang salah — sudah dibuktikan dengan merusaknya sengaja.
   (Saya sempat menulis sebaliknya di sini; keliru.)

   Jadi `onclause` di bawah bukan kehati-hatian berlebih: tanpanya kuerinya
   tidak terbentuk sama sekali. Yang perlu diingat adalah SEBABNYA, karena
   pesan galatnya menunjuk ke "tidak ada FK" dan bukan ke "FK-nya salah
   tabel" — dan yang membacanya akan mencari FK yang hilang, bukan FK yang
   keliru arah.

   Kolomnya tidak saya ubah dari sini: itu perubahan skema, dan
   memperbaikinya menyentuh seluruh pembaca `payment_incoming`.

YANG TIDAK TERCAKUP, DAN HARUS DISEBUTKAN

Kas keluar proyek hanya dapat dirunut lewat PEMBELIAN dan REIMBURSEMENT.
`expenses` dan `salary_slips` tidak punya kolom proyek sama sekali, jadi biaya
operasional dan gaji yang sebenarnya terpakai di proyek ini TIDAK ikut. Garis
kas keluarnya karena itu adalah batas bawah, bukan angka utuh — dan layarnya
wajib mengatakan itu, sebab pembaca yang mengira ini kas penuh akan
menyimpulkan proyeknya lebih sehat daripada keadaannya.
"""

from typing import Any, Dict, List

from sqlalchemy import select

from models.payment_incoming_model import payment_incoming_table
from models.payment_outgoing_model import payments_outgoing_table
from models.purchase_model import purchases_table
from models.reimbursement_model import reimbursements_table
from models.sales_invoice_model import sales_invoice_tables
from utils.database import database
from utils.errors import internal_error
from utils.logger_utils import log_error


def _baris(rows) -> List[Dict[str, Any]]:
    """`databases.Record` -> dict biasa.

    Record tidak punya `.get()`; mengembalikannya apa adanya ke controller
    membuat lapisan di atasnya melempar AttributeError yang — karena keluar di
    luar CORSMiddleware — sampai ke peramban sebagai keluhan CORS, bukan
    sebagai 500. Sudah pernah terjadi pada lencana menu.
    """
    return [dict(r) for r in rows]


class ProjectCashflowRepository:
    @staticmethod
    async def kas_keluar(project_name: str) -> List[Dict[str, Any]]:
        """
        Pembayaran keluar yang dapat dirunut ke proyek ini.

        Dua sumber, dikembalikan sebagai satu daftar dengan penanda `jenis`
        supaya layarnya dapat menjelaskan sebuah lonjakan tanpa permintaan
        kedua.
        """
        try:
            pembelian = select(
                payments_outgoing_table.c.date.label("date"),
                payments_outgoing_table.c.amount.label("amount"),
                purchases_table.c.invoiceName.label("acuan"),
            ).select_from(
                payments_outgoing_table.join(
                    purchases_table,
                    # onclause EKSPLISIT — lihat catatan (3) di kepala berkas.
                    payments_outgoing_table.c.purchaseID == purchases_table.c.id,
                )
            ).where(
                purchases_table.c.projectName == project_name,
                payments_outgoing_table.c.isDelete == False,  # noqa: E712
                purchases_table.c.isDelete == False,  # noqa: E712
            )

            reimburse = select(
                payments_outgoing_table.c.date.label("date"),
                payments_outgoing_table.c.amount.label("amount"),
                reimbursements_table.c.name.label("acuan"),
            ).select_from(
                payments_outgoing_table.join(
                    reimbursements_table,
                    payments_outgoing_table.c.reimbursementID
                    == reimbursements_table.c.id,
                )
            ).where(
                reimbursements_table.c.projectName == project_name,
                payments_outgoing_table.c.isDelete == False,  # noqa: E712
                reimbursements_table.c.isDelete == False,  # noqa: E712
            )

            hasil: List[Dict[str, Any]] = []
            for jenis, kueri in (("pembelian", pembelian), ("reimbursement", reimburse)):
                for b in _baris(await database.fetch_all(kueri)):
                    b["jenis"] = jenis
                    hasil.append(b)

            hasil.sort(key=lambda b: str(b["date"]))
            return hasil
        except Exception as e:
            log_error(f"Error fetching project cash outflow: {str(e)}")
            return internal_error()

    @staticmethod
    async def kas_masuk(project_name: str) -> List[Dict[str, Any]]:
        """Penerimaan atas faktur penjualan proyek ini."""
        try:
            kueri = select(
                payment_incoming_table.c.date.label("date"),
                payment_incoming_table.c.amount.label("amount"),
                sales_invoice_tables.c.name.label("acuan"),
            ).select_from(
                payment_incoming_table.join(
                    sales_invoice_tables,
                    # onclause EKSPLISIT. FK pada modelnya menunjuk
                    # `purchases.id` — lihat catatan (3) di kepala berkas.
                    payment_incoming_table.c.salesInvoiceID
                    == sales_invoice_tables.c.id,
                )
            ).where(
                sales_invoice_tables.c.projectName == project_name,
                payment_incoming_table.c.isDelete == False,  # noqa: E712
                sales_invoice_tables.c.isDelete == False,  # noqa: E712
            ).order_by(payment_incoming_table.c.date.asc())

            hasil = _baris(await database.fetch_all(kueri))
            for b in hasil:
                b["jenis"] = "faktur"
            return hasil
        except Exception as e:
            log_error(f"Error fetching project cash inflow: {str(e)}")
            return internal_error()
