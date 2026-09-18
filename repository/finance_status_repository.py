from datetime import date as d, timedelta
from typing import Any, Dict

from sqlalchemy import select, func, and_

from utils.database import database
from utils.logger_utils import log_error
from models.purchase_model import purchases_table, nilai_pembelian_sql
from models.sales_invoice_model import (
    sales_invoice_tables,
    nilai_faktur_sql,
    terbayar_faktur_sql,
)
from models.payment_outgoing_model import payments_outgoing_table
from models.payment_incoming_model import payment_incoming_table
from models.loans_model import loans_table
from models.dashboard_model import DashboardModel
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

# Berapa dokumen yang ikut dikirim bersama ringkasannya.
#
# Layar ini menjawab "siapa yang belum bayar", dan itu tidak terjawab oleh
# angka total. Tetapi daftar yang tidak berbatas dapat berisi ribuan baris
# pada perusahaan yang sudah lama berjalan — dan jawaban yang besarnya tidak
# terduga adalah jawaban yang suatu hari membuat layarnya diam.
#
# Yang terpotong DISEBUTKAN (`dokumenDipotong`), tidak dihilangkan diam-diam.
BATAS_DOKUMEN = 50


class FinanceStatusRepository:
    @staticmethod
    async def total_kas() -> Dict[str, Any]:
        """
        Kas yang BENAR-BENAR dapat dipakai, beserta yang dikecualikan.

        REKENING YANG DIKECUALIKAN TIDAK IKUT DIJUMLAH.

        Sebelumnya di sini `SUM(balance)` atas seluruh baris `balance` —
        termasuk rekening yang ditandai `excludeFromCalendar`, yaitu deposit
        jaminan dan sejenisnya: uang yang ada, tetapi tidak dapat
        dibelanjakan. Angka itu lalu menjadi pembilang quick ratio dan suku
        pertama modal kerja bersih, sehingga KEDUA ukuran kesehatan keuangan
        di layar ini tampak lebih baik daripada keadaannya, tanpa satu pun
        galat — dan lebih baik dengan selisih yang persis sebesar jaminan
        yang tidak boleh disentuh.

        Beranda sudah diperbaiki lebih dulu; halaman ini tertinggal. Karena
        itu sekarang keduanya membaca SATU sumber, `fetch_cash_position` —
        bukan dua hitungan yang kebetulan sependapat hari ini. Kalau tidak,
        beranda dan halaman posisi keuangan akan menyebut dua angka kas yang
        berbeda untuk perusahaan yang sama, dan tidak ada yang tahu mana yang
        berlaku.

        Yang dikecualikan tetap dikembalikan — uang yang dihilangkan dari
        laporan adalah uang yang tidak pernah dicocokkan lagi.
        """
        try:
            posisi = await DashboardModel.fetch_cash_position()
            if not isinstance(posisi, dict) or "error" in posisi:
                raise RuntimeError("posisi kas tidak dapat dibaca")
            return {
                "total": float(posisi.get("totalBalance") or 0),
                "dikecualikan": float(posisi.get("excludedBalance") or 0),
                "jumlahDikecualikan": int(posisi.get("excludedCount") or 0),
            }
        except Exception as e:
            log_error(f"Error menghitung total kas: {str(e)}")
            return {"total": 0.0, "dikecualikan": 0.0, "jumlahDikecualikan": 0}

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
            dokumen = []
            for r in rows:
                s = float(r["sisa"] or 0)
                total += s
                umur = (hari_ini - r["date"]).days if r["date"] else 0
                if umur <= 30:
                    kelompok = "0-30"
                elif umur <= 60:
                    kelompok = "31-60"
                elif umur <= 90:
                    kelompok = "61-90"
                else:
                    kelompok = "90+"
                ember[kelompok] += s
                dokumen.append(
                    {
                        "id": r["id"],
                        "nama": r["name"],
                        "tanggal": r["date"].isoformat() if r["date"] else None,
                        "proyek": r["projectName"],
                        "sisa": s,
                        "umurHari": umur,
                        "kelompok": kelompok,
                    }
                )

            # Yang TERTUA lebih dahulu — itu urutan menagihnya.
            #
            # Angka total menjawab "berapa", tetapi yang dikerjakan orang
            # besok pagi adalah menelepon SATU klien. Daftar tanpa urutan
            # memaksa yang membacanya mengurutkannya sendiri setiap kali.
            dokumen.sort(key=lambda x: -x["umurHari"])

            return {
                "total": total,
                "umur": ember,
                "jumlahDokumen": len(rows),
                "dokumen": dokumen[:BATAS_DOKUMEN],
                # Disebut supaya layar tidak diam-diam memperlihatkan
                # sebagian sebagai seluruhnya.
                "dokumenDipotong": len(dokumen) > BATAS_DOKUMEN,
            }
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
            dokumen = []
            for r in rows:
                s = float(r["sisa"] or 0)
                total += s
                if not r["dueDate"]:
                    # Tanpa tenggat, diperlakukan sebagai paling mendesak.
                    # Menganggapnya jauh membuat kewajiban nyata tersembunyi.
                    kelompok = "0-30"
                    selisih = None
                else:
                    selisih = (r["dueDate"] - hari_ini).days
                    if selisih < 0:
                        kelompok = "lewat"
                    elif selisih <= 30:
                        kelompok = "0-30"
                    elif selisih <= 60:
                        kelompok = "31-60"
                    else:
                        kelompok = "60+"
                ember[kelompok] += s
                dokumen.append(
                    {
                        "id": r["id"],
                        "nama": r["invoiceName"],
                        "jatuhTempo": (
                            r["dueDate"].isoformat() if r["dueDate"] else None
                        ),
                        "proyek": r["projectName"],
                        "sisa": s,
                        # Minus berarti SUDAH lewat sekian hari.
                        "sisaHari": selisih,
                        "kelompok": kelompok,
                    }
                )

            # Yang paling mendesak lebih dahulu. Tanpa tenggat dianggap
            # PALING mendesak — sama dengan perlakuannya pada pengemberan di
            # atas, supaya urutan daftar dan angka embernya tidak bercerita
            # dua hal yang berbeda.
            dokumen.sort(
                key=lambda x: (
                    x["sisaHari"] if x["sisaHari"] is not None else -10**6
                )
            )

            return {
                "total": total,
                "tempo": ember,
                "jumlahDokumen": len(rows),
                "dokumen": dokumen[:BATAS_DOKUMEN],
                "dokumenDipotong": len(dokumen) > BATAS_DOKUMEN,
            }
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

    # ------------------------------------------------------------------
    # Akurasi rencana kas
    # ------------------------------------------------------------------

    @staticmethod
    def _batas_bulan(mundur: int) -> Any:
        """
        Awal bulan sekarang dikurangi `mundur` bulan, dan awal bulan depan.

        Dihitung di Python, BUKAN dengan `EXTRACT(month)` di kueri: bentuk itu
        tidak dapat menyatakan rentang lintas tahun, dan ia membuat indeks
        `date` tidak terpakai. Batas atasnya EKSKLUSIF — ditentukan sekali di
        sini supaya tidak ada pemanggil yang menebaknya sendiri.
        """
        hari_ini = d.today()
        tahun, bulan = hari_ini.year, hari_ini.month

        t, b = tahun, bulan - mundur
        while b <= 0:
            b += 12
            t -= 1
        awal = d(t, b, 1)

        if bulan == 12:
            akhir = d(tahun + 1, 1, 1)
        else:
            akhir = d(tahun, bulan + 1, 1)
        return awal, akhir

    @staticmethod
    async def akurasi_rencana(mundur: int = 5) -> Dict[str, Any]:
        """
        Rencana kas dibandingkan dengan yang benar-benar terjadi.

        DUA PERTANYAAN YANG BERBEDA, dan keduanya dijawab terpisah — sengaja.

        1. CAKUPAN (`disposisi`): dari rencana yang pernah dibuat, berapa yang
           akhirnya ditandai terpakai, berapa dibatalkan, dan berapa yang
           tanggalnya sudah lewat tetapi tidak pernah disentuh lagi. Inilah
           yang menjawab "rencana kas saya dapat dipercaya atau tidak".

        2. BESARAN (`bulanan`): berapa yang direncanakan bergerak tiap bulan
           dan berapa yang benar-benar bergerak.

        KENAPA KEDUANYA TIDAK DIJADIKAN SATU PERSENTASE

        `aktual` memuat SELURUH kas yang bergerak, termasuk yang tidak pernah
        direncanakan sama sekali. Jadi `aktual / rencana` bukan akurasi: bulan
        yang rencananya meleset jauh tetapi kebetulan ada pembayaran besar di
        luar rencana akan tampak "100% akurat". Angka tunggal seperti itu
        terbaca pasti justru karena tidak ada yang dapat memeriksanya.

        Rencana berstatus `batal` TIDAK dihitung pada `bulanan`: ia memang
        sengaja ditiadakan, bukan rencana yang meleset. Ia tetap muncul di
        `disposisi`, karena berapa banyak yang dibatalkan justru bagian dari
        jawabannya.
        """
        try:
            awal, akhir = FinanceStatusRepository._batas_bulan(mundur)

            async def _per_bulan(sql: str, param: Dict[str, Any]):
                rows = await database.fetch_all(sql, param)
                return {r["bulan"]: float(r["total"] or 0) for r in rows}

            waktu = {"awal": awal, "akhir": akhir}

            rencana_keluar = await _per_bulan(
                """
                SELECT DATE_FORMAT(date, '%Y-%m') AS bulan,
                       SUM(amount) AS total
                FROM payment_plans
                WHERE isDelete = 0 AND status <> 'batal'
                  AND planType = 'keluar'
                  AND date >= :awal AND date < :akhir
                GROUP BY DATE_FORMAT(date, '%Y-%m')
                """,
                waktu,
            )
            rencana_masuk = await _per_bulan(
                """
                SELECT DATE_FORMAT(date, '%Y-%m') AS bulan,
                       SUM(amount) AS total
                FROM payment_plans
                WHERE isDelete = 0 AND status <> 'batal'
                  AND planType = 'masuk'
                  AND date >= :awal AND date < :akhir
                GROUP BY DATE_FORMAT(date, '%Y-%m')
                """,
                waktu,
            )
            # HANYA yang sudah disetujui: pengajuan yang belum disetujui
            # belum menggerakkan uang, dan memasukkannya membuat "aktual"
            # menyebut kas yang masih ada di rekening.
            aktual_keluar = await _per_bulan(
                """
                SELECT DATE_FORMAT(date, '%Y-%m') AS bulan,
                       SUM(amount) AS total
                FROM payments_outgoing
                WHERE isDelete = 0 AND isApprove = 1
                  AND date >= :awal AND date < :akhir
                GROUP BY DATE_FORMAT(date, '%Y-%m')
                """,
                waktu,
            )
            aktual_masuk = await _per_bulan(
                """
                SELECT DATE_FORMAT(date, '%Y-%m') AS bulan,
                       SUM(amount) AS total
                FROM payment_incoming
                WHERE isDelete = 0 AND isApprove = 1
                  AND date >= :awal AND date < :akhir
                GROUP BY DATE_FORMAT(date, '%Y-%m')
                """,
                waktu,
            )

            # Seluruh bulan dalam rentang DIGAMBAR, termasuk yang kosong.
            # Bulan yang hilang dari grafik terbaca sebagai bulan yang tidak
            # ada, bukan sebagai bulan yang tidak bergerak.
            bulanan = []
            t, b = awal.year, awal.month
            while d(t, b, 1) < akhir:
                kunci = f"{t:04d}-{b:02d}"
                bulanan.append(
                    {
                        "bulan": kunci,
                        "rencanaKeluar": rencana_keluar.get(kunci, 0.0),
                        "rencanaMasuk": rencana_masuk.get(kunci, 0.0),
                        "aktualKeluar": aktual_keluar.get(kunci, 0.0),
                        "aktualMasuk": aktual_masuk.get(kunci, 0.0),
                    }
                )
                b += 1
                if b > 12:
                    b = 1
                    t += 1

            disposisi_rows = await database.fetch_all(
                """
                SELECT status, COUNT(*) AS jumlah, SUM(amount) AS total
                FROM payment_plans
                WHERE isDelete = 0
                  AND date >= :awal AND date < :akhir
                GROUP BY status
                """,
                waktu,
            )
            disposisi = {
                str(r["status"]): {
                    "jumlah": int(r["jumlah"] or 0),
                    "total": float(r["total"] or 0),
                }
                for r in disposisi_rows
            }

            # Rencana yang tanggalnya SUDAH LEWAT tetapi statusnya masih
            # `rencana`: tidak pernah ditandai terpakai, tidak pernah
            # dibatalkan. Ia tidak menghasilkan galat apa pun — ia hanya
            # menggantung, dan setiap proyeksi kas yang memakainya menghitung
            # uang yang tidak akan bergerak ke mana pun.
            gantung = await database.fetch_one(
                """
                SELECT COUNT(*) AS jumlah, COALESCE(SUM(amount), 0) AS total
                FROM payment_plans
                WHERE isDelete = 0 AND status = 'rencana' AND date < :hari_ini
                """,
                {"hari_ini": d.today()},
            )

            return {
                "bulanan": bulanan,
                "disposisi": disposisi,
                "menggantung": {
                    "jumlah": int(gantung["jumlah"] or 0) if gantung else 0,
                    "total": float(gantung["total"] or 0) if gantung else 0.0,
                },
                "periode": {
                    "awal": awal.isoformat(),
                    # Dikembalikan INKLUSIF untuk dibaca orang; batas kueri di
                    # atas tetap eksklusif. Menyebut tanggal 1 bulan depan
                    # sebagai akhir periode membuat layar mencetak rentang
                    # yang satu hari lebih panjang daripada yang dihitung.
                    "akhir": (akhir - timedelta(days=1)).isoformat(),
                },
            }
        except Exception as e:
            log_error(f"Error menghitung akurasi rencana: {str(e)}")
            return {
                "bulanan": [],
                "disposisi": {},
                "menggantung": {"jumlah": 0, "total": 0.0},
                "error": ErrorCode.INTERNAL,
            }
