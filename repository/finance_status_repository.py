from datetime import date as d, timedelta, datetime as dt
from typing import Any, Dict

from sqlalchemy import select, func, and_
from sqlalchemy.dialects.mysql import insert as mysql_insert

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
from models.payment_plan_model import payment_plans_table
from models.loans_model import loans_table
from models.dashboard_model import DashboardModel
from models.expense_model import expenses_table
from models.reimbursement_model import (
    reimbursements_table,
    reimbursement_items_table,
)
from models.asset_model import asset_table
from models.finance_threshold_model import finance_thresholds_table
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


#: Nama tabel untuk kueri SQL MENTAH — diambil dari modelnya, tidak diketik.
#:
#: Dua kueri di berkas ini sempat menyebut `payments_outgoing`, sementara
#: tabelnya bernama `payment_outgoing`. Yang terjadi BUKAN galat di layar:
#: `try/except` di sekelilingnya menangkapnya dan mengembalikan nol, sehingga
#: "aktual keluar" pada grafik akurasi rencana berbunyi NOL untuk setiap
#: bulan, dan gaji yang belum cair tidak pernah muncul sebagai kewajiban.
#: Grafik yang seluruh batangnya nol terbaca sebagai bulan yang memang tidak
#: bergerak.
#:
#: Diambil dari objek modelnya supaya penggantian nama di sana ikut terbawa,
#: dan supaya tidak ada nama tabel yang dapat mengetik dirinya sendiri keliru.
TABEL_KELUAR = payments_outgoing_table.name
TABEL_MASUK = payment_incoming_table.name
TABEL_RENCANA = payment_plans_table.name
TABEL_FAKTUR = sales_invoice_tables.name


#: Pita acuan BAWAAN tiap rasio.
#:
#: Sumbernya disebut per baris supaya yang membaca angkanya dapat
#: menimbangnya sendiri. CFMA = Construction Financial Management
#: Association, konstruksi Amerika, lintas jenis usaha — ORIENTASI, bukan
#: vonis, dan tidak disusun dari subkontraktor di Indonesia.
#:
#: `None` berarti sisi itu memang tidak dibatasi: DSO tidak punya batas bawah
#: yang bermakna (tertagih lebih cepat selalu lebih baik), dan marjin tidak
#: punya batas atas.
#: Arah tiap rasio — MANA yang lebih baik saat angkanya naik.
#:
#: Tanpa ini, "di luar acuan" tidak dapat diterjemahkan menjadi bagus atau
#: tidak. Marjin 25% di atas pita adalah kabar baik; DSO 130 hari di atas
#: pita adalah kabar buruk. Menyamakan keduanya membuat layar memberi tanda
#: yang sama untuk dua keadaan yang berlawanan.
#:
#:   "naikBaik"   -> makin tinggi makin baik (marjin, ROE)
#:   "naikBuruk"  -> makin tinggi makin buruk (DSO, utang, konsentrasi)
#:   "pita"       -> dua sisinya sama-sama berarti (quick ratio: terlalu
#:                   rendah berarti tidak mampu bayar, terlalu tinggi berarti
#:                   kas menganggur)
ARAH: Dict[str, str] = {
    "quickRatio": "pita",
    "debtToEquity": "naikBuruk",
    "dso": "naikBuruk",
    "dpo": "naikBaik",
    "siklusModalKerja": "naikBuruk",
    "piutangTua": "naikBuruk",
    "konsentrasiPiutang": "naikBuruk",
    "marjinKotor": "naikBaik",
    "marjinBersih": "naikBaik",
    "rasioOverhead": "naikBuruk",
    "roe": "naikBaik",
}

AMBANG_BAWAAN: Dict[str, Dict[str, Any]] = {
    # Likuiditas
    "quickRatio": {"bawah": 1.1, "atas": 1.5, "acuan": "CFMA"},
    "debtToEquity": {"bawah": 0.5, "atas": 1.5, "acuan": "CFMA"},
    # Perputaran, dalam HARI. Konstruksi memang lambat: penagihan bertahap,
    # retensi 5-10% ditahan sampai selesai, dan rantai pemilik-kontraktor
    # utama-subkontraktor. 72 hari rata-rata, wajar 55-95.
    "dso": {"bawah": None, "atas": 95.0, "acuan": "Hackett/CRF 2025-2026"},
    "dpo": {"bawah": None, "atas": None, "acuan": "pasangan DSO"},
    "siklusModalKerja": {"bawah": None, "atas": 60.0, "acuan": "turunan"},
    # Bagian piutang yang sudah lewat 90 hari.
    "piutangTua": {"bawah": None, "atas": 0.15, "acuan": "kebiasaan"},
    # Bagian piutang yang menumpuk pada SATU klien.
    "konsentrasiPiutang": {"bawah": None, "atas": 0.40, "acuan": "kebiasaan"},
    # Marjin — pecahan, bukan persen. Kontraktor umum 12-16%, spesialis
    # 15-25%; AKN subkontraktor MEP, jadi bawaannya mengambil yang spesialis.
    "marjinKotor": {"bawah": 0.15, "atas": None, "acuan": "CFMA"},
    "marjinBersih": {"bawah": 0.05, "atas": None, "acuan": "CFMA"},
    "rasioOverhead": {"bawah": None, "atas": 0.15, "acuan": "CFMA"},
    "roe": {"bawah": 0.10, "atas": None, "acuan": "CFMA"},
}


def _ringkas(baris) -> Dict[str, Any]:
    """Satu baris agregat (SUM, COUNT) menjadi bentuk yang seragam."""
    if not baris:
        return {"total": 0.0, "jumlahDokumen": 0}
    r = baris[0]
    nilai = list(r.values()) if hasattr(r, "values") else list(r)
    return {
        "total": float(nilai[0] or 0),
        "jumlahDokumen": int(nilai[1] or 0),
    }


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
                        # PEMBELIAN INTERNAL BUKAN UTANG.
                        #
                        # `isInternal` menandai dokumen kepentingan sendiri —
                        # tidak ada pemasok luar yang menagih, dan
                        # `purchase_controller` malah langsung menyetelnya
                        # `isPaid`. Tetapi utang di sini dihitung sebagai
                        # `nilai - yang dibayarkan`, dan pembelian internal
                        # memang tidak punya baris pembayaran sama sekali —
                        # jadi SELURUH nilainya muncul sebagai utang yang
                        # tidak akan pernah tertutup oleh apa pun.
                        #
                        # Akibatnya utang usaha membesar, quick ratio dan
                        # modal kerja bersih mengecil, dan kewajiban 30 hari
                        # menyebut uang yang tidak akan dibayarkan ke mana
                        # pun. Tidak ada galat; angkanya saja yang salah.
                        #
                        # `laba_rugi_repository` dan
                        # `PurchaseRepository.belum_dibayar` sudah
                        # mengecualikannya sejak awal — hanya di sini yang
                        # tertinggal.
                        purchases_table.c.isInternal == False,  # noqa: E712
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
                f"""
                SELECT DATE_FORMAT(date, '%Y-%m') AS bulan,
                       SUM(amount) AS total
                FROM {TABEL_RENCANA}
                WHERE isDelete = 0 AND status <> 'batal'
                  AND planType = 'keluar'
                  AND date >= :awal AND date < :akhir
                GROUP BY DATE_FORMAT(date, '%Y-%m')
                """,
                waktu,
            )
            rencana_masuk = await _per_bulan(
                f"""
                SELECT DATE_FORMAT(date, '%Y-%m') AS bulan,
                       SUM(amount) AS total
                FROM {TABEL_RENCANA}
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
                f"""
                SELECT DATE_FORMAT(date, '%Y-%m') AS bulan,
                       SUM(amount) AS total
                FROM {TABEL_KELUAR}
                WHERE isDelete = 0 AND isApprove = 1
                  AND date >= :awal AND date < :akhir
                GROUP BY DATE_FORMAT(date, '%Y-%m')
                """,
                waktu,
            )
            aktual_masuk = await _per_bulan(
                f"""
                SELECT DATE_FORMAT(date, '%Y-%m') AS bulan,
                       SUM(amount) AS total
                FROM {TABEL_MASUK}
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
                f"""
                SELECT status, COUNT(*) AS jumlah, SUM(amount) AS total
                FROM {TABEL_RENCANA}
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
                f"""
                SELECT COUNT(*) AS jumlah, COALESCE(SUM(amount), 0) AS total
                FROM {TABEL_RENCANA}
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

    # ------------------------------------------------------------------
    # Kewajiban selain utang usaha
    # ------------------------------------------------------------------

    @staticmethod
    async def kewajiban_lain() -> Dict[str, Any]:
        """
        Beban, reimbursement, dan slip gaji yang BELUM dibayarkan.

        KENAPA INI PERLU ADA

        `utang_usaha()` hanya membaca `purchases`. Tetapi `payments_outgoing`
        dapat menunjuk LIMA jenis dokumen — pembelian, beban, reimbursement,
        slip gaji, dan angsuran pinjaman — dan empat di antaranya adalah
        kewajiban kepada pihak luar yang sama nyatanya.

        Selama hanya pembelian yang dihitung, "utang usaha" di layar posisi
        keuangan menyebut angka yang lebih kecil daripada yang benar-benar
        harus dibayar, dan quick ratio serta modal kerja bersih yang disusun
        di atasnya tampak lebih baik daripada keadaannya. Gaji bulan berjalan
        yang belum cair tidak muncul sebagai kewajiban sama sekali.

        NILAINYA MEMAKAI RUMUS YANG SAMA dengan yang dipakai saat
        MENYETUJUI pembayaran (`payment_outgoing_controller.nilai_beban` dan
        `nilai_slip`). Bila ditulis ulang di sini dengan suku yang berbeda,
        dokumen yang sama akan dianggap lunas oleh satu bagian sistem dan
        masih berutang oleh bagian yang lain — persis kekeliruan yang
        `nilai_pembelian_sql` dibuat untuk menghentikannya.
        """
        try:
            hasil: Dict[str, Any] = {}

            # --- Beban: DPP + PBBKB - PPh. PPN TIDAK ikut (disetor
            #     terpisah), sama seperti `nilai_beban`.
            e = expenses_table.c
            bayar_beban = (
                select(
                    payments_outgoing_table.c.expenseID.label("doc"),
                    func.coalesce(
                        func.sum(payments_outgoing_table.c.amount), 0
                    ).label("dibayar"),
                )
                .where(
                    payments_outgoing_table.c.isDelete == False,  # noqa: E712
                    payments_outgoing_table.c.isApprove == True,  # noqa: E712
                )
                .group_by(payments_outgoing_table.c.expenseID)
                .subquery()
            )
            nilai_beban = (
                func.coalesce(e.dpp, 0)
                + func.coalesce(e.pbbkb, 0)
                - func.coalesce(e.pphPercentage, 0) * func.coalesce(e.dpp, 0) / 100
            )
            sisa_beban = nilai_beban - func.coalesce(bayar_beban.c.dibayar, 0)
            baris = await database.fetch_all(
                select(func.coalesce(func.sum(sisa_beban), 0), func.count())
                .select_from(
                    expenses_table.outerjoin(
                        bayar_beban, bayar_beban.c.doc == e.id
                    )
                )
                .where(
                    and_(
                        e.isDelete == False,  # noqa: E712
                        sisa_beban > TOLERANSI_LUNAS,
                    )
                )
            )
            hasil["beban"] = _ringkas(baris)

            # --- Reimbursement: jumlah barisnya sendiri.
            #     HANYA yang sudah disetujui — pengajuan yang belum disetujui
            #     belum menjadi kewajiban siapa pun.
            r = reimbursements_table.c
            nilai_reimb = (
                select(
                    reimbursement_items_table.c.reimbursementID.label("doc"),
                    func.coalesce(
                        func.sum(reimbursement_items_table.c.amount), 0
                    ).label("nilai"),
                )
                .group_by(reimbursement_items_table.c.reimbursementID)
                .subquery()
            )
            bayar_reimb = (
                select(
                    payments_outgoing_table.c.reimbursementID.label("doc"),
                    func.coalesce(
                        func.sum(payments_outgoing_table.c.amount), 0
                    ).label("dibayar"),
                )
                .where(
                    payments_outgoing_table.c.isDelete == False,  # noqa: E712
                    payments_outgoing_table.c.isApprove == True,  # noqa: E712
                )
                .group_by(payments_outgoing_table.c.reimbursementID)
                .subquery()
            )
            sisa_reimb = func.coalesce(nilai_reimb.c.nilai, 0) - func.coalesce(
                bayar_reimb.c.dibayar, 0
            )
            baris = await database.fetch_all(
                select(func.coalesce(func.sum(sisa_reimb), 0), func.count())
                .select_from(
                    reimbursements_table.outerjoin(
                        nilai_reimb, nilai_reimb.c.doc == r.id
                    ).outerjoin(bayar_reimb, bayar_reimb.c.doc == r.id)
                )
                .where(
                    and_(
                        r.isDelete == False,  # noqa: E712
                        r.isApprove == True,  # noqa: E712
                        sisa_reimb > TOLERANSI_LUNAS,
                    )
                )
            )
            hasil["reimbursement"] = _ringkas(baris)

            # --- Slip gaji: pokok + tunjangan - potongan - pajak.
            #     `salary_slips` TIDAK punya kolom total; nilainya memang
            #     dihitung dari komponennya. Yang membaca `slip["total"]`
            #     akan jatuh ke nol untuk SETIAP slip.
            hasil["gaji"] = await FinanceStatusRepository._gaji_belum_dibayar()

            total = sum(float(v["total"]) for v in hasil.values())
            jumlah = sum(int(v["jumlahDokumen"]) for v in hasil.values())
            return {"total": total, "jumlahDokumen": jumlah, "rincian": hasil}
        except Exception as e:
            log_error(f"Error menghitung kewajiban lain: {str(e)}")
            return {
                "total": 0.0,
                "jumlahDokumen": 0,
                "rincian": {},
                "error": ErrorCode.INTERNAL,
            }

    @staticmethod
    async def _gaji_belum_dibayar() -> Dict[str, Any]:
        """
        Slip gaji yang belum cair, dengan rumus `nilai_slip`.

        Tunjangan dan potongan disaring `isIncluded`: baris yang tidak
        disertakan memang tercantum di slip untuk dibaca, tetapi tidak ikut
        menambah atau mengurangi yang dibayarkan.
        """
        rows = await database.fetch_all(
            f"""
            SELECT s.id,
                   COALESCE(s.basicSalary, 0)
                 + COALESCE(s.transportationAllowanceRate, 0)
                   * COALESCE(s.transportationAllowanceQuantity, 0)
                 + COALESCE(s.mealAllowanceRate, 0)
                   * COALESCE(s.mealAllowanceQuantity, 0)
                 + COALESCE(s.overtimeRate, 0) * COALESCE(s.overtimeQuantity, 0)
                 + COALESCE(t.total, 0)
                 - COALESCE(p.total, 0)
                 - COALESCE(s.taxAmount, 0)
                 - COALESCE(b.dibayar, 0) AS sisa
            FROM salary_slips s
            LEFT JOIN (
                SELECT salarySlipID, SUM(amount) AS total
                FROM salary_slips_allowances WHERE isIncluded = 1
                GROUP BY salarySlipID
            ) t ON t.salarySlipID = s.id
            LEFT JOIN (
                SELECT salarySlipID, SUM(amount) AS total
                FROM salary_slips_deductions WHERE isIncluded = 1
                GROUP BY salarySlipID
            ) p ON p.salarySlipID = s.id
            LEFT JOIN (
                SELECT salarySlipID, SUM(amount) AS dibayar
                FROM {TABEL_KELUAR}
                WHERE isDelete = 0 AND isApprove = 1
                GROUP BY salarySlipID
            ) b ON b.salarySlipID = s.id
            WHERE s.isDelete = 0
            HAVING sisa > :toleransi
            """,
            {"toleransi": TOLERANSI_LUNAS},
        )
        total = sum(float(r["sisa"] or 0) for r in rows)
        return {"total": total, "jumlahDokumen": len(rows)}

    # ------------------------------------------------------------------
    # Aset tetap
    # ------------------------------------------------------------------

    @staticmethod
    async def nilai_buku_aset() -> Dict[str, Any]:
        """
        Nilai buku aset tetap: perolehan dikurangi penyusutan terkumpul.

        Garis lurus ke nol tanpa nilai sisa, memakai masa manfaat pada kolom
        `depreciation` (dalam TAHUN) — metode yang SAMA dengan
        `laba_rugi_repository._penyusutan_rentang`. Aset bermasa manfaat 0
        (mis. tanah) tidak disusutkan, dan aset yang sudah dijual tidak
        dihitung lagi.

        CATATAN yang harus ikut tercetak: sebagian pembelian aset juga
        tercatat sebagai beban langsung kategori 5.1.1 alih-alih
        dikapitalisasi. Bila begitu, asetnya muncul di sini SEKALIGUS sudah
        membebani laba rugi — dan laba rugi sudah menandai selisih itu.
        Angkanya karena itu perkiraan, bukan angka pembukuan.
        """
        try:
            hari_ini = d.today()
            rows = await database.fetch_all(
                select(
                    asset_table.c.value,
                    asset_table.c.depreciation,
                    asset_table.c.purchaseDate,
                    asset_table.c.soldDate,
                ).where(asset_table.c.purchaseDate <= hari_ini)
            )

            perolehan = 0.0
            nilai_buku = 0.0
            jumlah = 0
            idx_kini = hari_ini.year * 12 + hari_ini.month
            for r in rows:
                if r["soldDate"] is not None:
                    continue
                nilai = float(r["value"] or 0)
                tahun = int(r["depreciation"] or 0)
                pd = r["purchaseDate"]
                if nilai <= 0 or pd is None:
                    continue
                jumlah += 1
                perolehan += nilai
                if tahun <= 0:
                    # Tidak disusutkan (mis. tanah): nilai bukunya tetap.
                    nilai_buku += nilai
                    continue
                # Bulan perolehan IKUT disusutkan, sama seperti laba rugi.
                bulan_jalan = idx_kini - (pd.year * 12 + pd.month) + 1
                bulan_jalan = max(0, min(bulan_jalan, tahun * 12))
                akumulasi = nilai / (tahun * 12) * bulan_jalan
                nilai_buku += max(0.0, nilai - akumulasi)

            return {
                "nilaiBuku": round(nilai_buku, 2),
                "perolehan": round(perolehan, 2),
                "akumulasiPenyusutan": round(perolehan - nilai_buku, 2),
                "jumlahAset": jumlah,
            }
        except Exception as e:
            log_error(f"Error menghitung nilai buku aset: {str(e)}")
            return {
                "nilaiBuku": 0.0,
                "perolehan": 0.0,
                "akumulasiPenyusutan": 0.0,
                "jumlahAset": 0,
                "error": ErrorCode.INTERNAL,
            }

    # ------------------------------------------------------------------
    # Pita acuan
    # ------------------------------------------------------------------

    @staticmethod
    async def ambang() -> Dict[str, Dict[str, Any]]:
        """
        Pita acuan tiap rasio: bawaan, ditimpa oleh yang disimpan.

        BAWAANNYA DI KODE, bukan di basis data. Tabelnya hanya menyimpan yang
        DIUBAH. Dua akibatnya disengaja: tabel yang kosong sama sekali tetap
        menghasilkan halaman yang benar — tidak ada langkah penyemaian yang
        bila terlewat membuat seluruh pita menjadi nol — dan menghapus satu
        baris MENGEMBALIKAN bawaannya alih-alih menghapus pitanya.

        Kegagalan membaca tabelnya TIDAK menjatuhkan apa pun: yang kembali
        bawaannya, dan `sumber` menyebut bahwa yang berlaku bawaan. Pita yang
        gagal dibaca lalu diam-diam menjadi nol akan menandai setiap rasio
        sebagai di luar acuan.
        """
        hasil = {
            kode: {
                **nilai,
                "sumber": "bawaan",
                # Arah dikirim bersama pitanya: layar tidak boleh
                # memutuskannya sendiri, sebab dua tempat yang memutuskan
                # akan berselisih — dan selisihnya berupa tanda BAIK pada
                # angka yang buruk.
                "arah": ARAH.get(kode, "pita"),
            }
            for kode, nilai in AMBANG_BAWAAN.items()
        }
        try:
            rows = await database.fetch_all(
                select(
                    finance_thresholds_table.c.kode,
                    finance_thresholds_table.c.bawah,
                    finance_thresholds_table.c.atas,
                )
            )
            for r in rows:
                kode = str(r["kode"])
                if kode not in hasil:
                    # Kode yang tidak dikenal DIABAIKAN, bukan ikut dikirim.
                    # Sisa dari rasio yang pernah ada lalu dibuang tidak boleh
                    # muncul sebagai pita tanpa angka yang mengikutinya.
                    continue
                hasil[kode] = {
                    **hasil[kode],
                    "bawah": (
                        float(r["bawah"]) if r["bawah"] is not None else None
                    ),
                    "atas": float(r["atas"]) if r["atas"] is not None else None,
                    "sumber": "disetel",
                }
        except Exception as e:
            log_error(f"Error membaca ambang keuangan: {str(e)}")
        return hasil

    @staticmethod
    async def simpan_ambang(
        kode: str, bawah: Any, atas: Any, user_id: int
    ) -> Dict[str, Any]:
        """Simpan satu pita; menimpa bila kodenya sudah ada."""
        try:
            if kode not in AMBANG_BAWAAN:
                return {"error": ErrorCode.VALIDATION, "kode": kode}
            await database.execute(
                mysql_insert(finance_thresholds_table)
                .values(
                    kode=kode,
                    bawah=bawah,
                    atas=atas,
                    updatedAt=dt.now(),
                    updatedBy=user_id,
                )
                .on_duplicate_key_update(
                    bawah=bawah,
                    atas=atas,
                    updatedAt=dt.now(),
                    updatedBy=user_id,
                )
            )
            return {"ok": True}
        except Exception as e:
            log_error(f"Error menyimpan ambang keuangan: {str(e)}")
            return {"error": ErrorCode.INTERNAL}

    @staticmethod
    async def hapus_ambang(kode: str) -> Dict[str, Any]:
        """
        Kembalikan satu pita ke bawaannya.

        MENGHAPUS BARISNYA, bukan menuliskan angka bawaan ke dalamnya. Bila
        bawaan di kode kelak diperbarui, pita yang "dikembalikan" dengan cara
        menulis angka justru membeku pada angka lama — dan tidak ada yang
        dapat membedakannya dari pita yang memang sengaja disetel begitu.
        """
        try:
            await database.execute(
                finance_thresholds_table.delete().where(
                    finance_thresholds_table.c.kode == kode
                )
            )
            return {"ok": True}
        except Exception as e:
            log_error(f"Error menghapus ambang keuangan: {str(e)}")
            return {"error": ErrorCode.INTERNAL}

    # ------------------------------------------------------------------
    # Perputaran & konsentrasi
    # ------------------------------------------------------------------

    @staticmethod
    async def arus_setahun() -> Dict[str, Any]:
        """
        Pendapatan dan pembelian 12 bulan terakhir — penyebut DSO dan DPO.

        DUA BELAS BULAN, bukan bulan berjalan. Pendapatan kontraktor datang
        bergelombang mengikuti termin; membagi piutang dengan pendapatan satu
        bulan menghasilkan DSO yang melompat-lompat antara belasan dan
        ratusan hari, dan angka yang melompat berhenti dipercaya.

        Pendapatan diambil dari faktur yang SUDAH DISETUJUI — sama dengan
        syarat `piutang()`. Bila pembilang dan penyebutnya menyaring berbeda,
        DSO-nya menghitung piutang atas pendapatan yang tidak memuatnya.
        """
        try:
            hari_ini = d.today()
            awal = hari_ini - timedelta(days=365)

            pendapatan = await database.fetch_val(
                select(func.coalesce(func.sum(nilai_faktur_sql()), 0)).where(
                    and_(
                        sales_invoice_tables.c.isDelete == False,  # noqa: E712
                        sales_invoice_tables.c.isApprove == True,  # noqa: E712
                        sales_invoice_tables.c.date >= awal,
                        sales_invoice_tables.c.date <= hari_ini,
                    )
                )
            )
            pembelian = await database.fetch_val(
                select(func.coalesce(func.sum(nilai_pembelian_sql()), 0)).where(
                    and_(
                        purchases_table.c.isDelete == False,  # noqa: E712
                        # Internal bukan pembelian kepada pihak luar, jadi ia
                        # bukan penyebut umur bayar. Sama dengan
                        # `utang_usaha()`, supaya DPO tidak membandingkan
                        # utang yang menyaringnya dengan pembelian yang tidak.
                        purchases_table.c.isInternal == False,  # noqa: E712
                        purchases_table.c.date >= awal,
                        purchases_table.c.date <= hari_ini,
                    )
                )
            )
            return {
                "pendapatan": float(pendapatan or 0),
                "pembelian": float(pembelian or 0),
                "hari": 365,
                "sejak": awal.isoformat(),
            }
        except Exception as e:
            log_error(f"Error menghitung arus setahun: {str(e)}")
            return {
                "pendapatan": 0.0,
                "pembelian": 0.0,
                "hari": 365,
                "error": ErrorCode.INTERNAL,
            }

    @staticmethod
    async def konsentrasi_piutang() -> Dict[str, Any]:
        """
        Berapa bagian piutang yang menumpuk pada SATU klien.

        Rasio likuiditas tidak dapat melihat ini: piutang Rp 2 miliar yang
        tersebar pada delapan klien dan yang seluruhnya pada satu klien
        menghasilkan quick ratio yang sama persis — padahal yang kedua
        berarti satu klien yang terlambat membuat kas perusahaan berhenti.
        """
        try:
            bayar = terbayar_faktur_sql()
            nilai = nilai_faktur_sql()
            sisa = nilai - func.coalesce(bayar.c.total_paid, 0)

            rows = await database.fetch_all(
                select(
                    sales_invoice_tables.c.clientID,
                    func.coalesce(func.sum(sisa), 0).label("sisa"),
                )
                .select_from(
                    sales_invoice_tables.outerjoin(
                        bayar, bayar.c.invoice_id == sales_invoice_tables.c.id
                    )
                )
                .where(
                    and_(
                        sales_invoice_tables.c.isDelete == False,  # noqa: E712
                        sales_invoice_tables.c.isApprove == True,  # noqa: E712
                        sisa > TOLERANSI_LUNAS,
                    )
                )
                .group_by(sales_invoice_tables.c.clientID)
            )

            per_klien = sorted(
                (
                    {
                        "clientID": r["clientID"],
                        "sisa": float(r["sisa"] or 0),
                    }
                    for r in rows
                ),
                key=lambda x: -x["sisa"],
            )
            total = sum(x["sisa"] for x in per_klien)
            teratas = per_klien[0] if per_klien else None
            return {
                "jumlahKlien": len(per_klien),
                "total": total,
                "terbesar": teratas,
                # `None`, BUKAN nol, saat belum ada piutang sama sekali:
                # "0% terkonsentrasi" pada perusahaan tanpa piutang adalah
                # pengukuran atas sesuatu yang tidak ada.
                "bagianTerbesar": (
                    (teratas["sisa"] / total) if teratas and total > 0 else None
                ),
            }
        except Exception as e:
            log_error(f"Error menghitung konsentrasi piutang: {str(e)}")
            return {
                "jumlahKlien": 0,
                "total": 0.0,
                "terbesar": None,
                "bagianTerbesar": None,
                "error": ErrorCode.INTERNAL,
            }

    @staticmethod
    async def backlog() -> Dict[str, Any]:
        """
        Nilai kontrak proyek BERJALAN yang belum difakturkan.

        Inilah pekerjaan yang sudah dipegang tetapi belum menjadi uang — satu
        angka yang tidak terlihat di rasio mana pun, dan yang paling sering
        ditanya: "kerjaan kita masih ada berapa".

        "Berjalan" memakai definisi yang SAMA dengan daftar proyek
        (`isActive` dan bukan batal dan bukan menunggu retensi). Bila layar
        ini memakai definisi sendiri, dua halaman akan menyebut jumlah proyek
        yang berbeda untuk perusahaan yang sama.

        Nilai kontrak memakai DPP: PPN titipan negara dan bukan pendapatan.
        Adendum IKUT — ia memang menambah nilai kontrak.
        """
        try:
            nilai_kontrak = await database.fetch_val(
                """
                SELECT COALESCE(SUM(k.dpp), 0)
                FROM project_contracts k
                JOIN projects p ON p.id = k.projectID
                WHERE p.isDelete = 0
                  AND p.isActive = 1
                  AND p.isCancelled = 0
                  AND p.isRetention = 0
                """
            )
            # Yang SUDAH difakturkan atas proyek-proyek itu.
            difakturkan = await database.fetch_val(
                f"""
                SELECT COALESCE(SUM(f.dpp), 0)
                FROM {TABEL_FAKTUR} f
                JOIN projects p ON p.code = f.projectName
                WHERE f.isDelete = 0
                  AND f.isApprove = 1
                  AND p.isDelete = 0
                  AND p.isActive = 1
                  AND p.isCancelled = 0
                  AND p.isRetention = 0
                """
            )
            kontrak = float(nilai_kontrak or 0)
            sudah = float(difakturkan or 0)
            return {
                "nilaiKontrak": kontrak,
                "sudahDifakturkan": sudah,
                # Dijepit pada nol: faktur dapat melampaui nilai kontrak bila
                # adendumnya belum sempat dicatat, dan backlog minus terbaca
                # sebagai kesalahan hitung, bukan sebagai dokumen yang
                # tertinggal.
                "belumDifakturkan": max(0.0, kontrak - sudah),
                "kontrakMelampauiNilai": sudah > kontrak,
            }
        except Exception as e:
            log_error(f"Error menghitung backlog: {str(e)}")
            return {
                "nilaiKontrak": 0.0,
                "sudahDifakturkan": 0.0,
                "belumDifakturkan": 0.0,
                "kontrakMelampauiNilai": False,
                "error": ErrorCode.INTERNAL,
            }
