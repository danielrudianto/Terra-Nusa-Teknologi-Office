"""
KPI perusahaan — angka laba rugi per bulan, dalam SATU set kueri.

KENAPA BERKAS INI ADA

`LabaRugiRepository.laba_rugi(bulan, tahun)` sudah menyusun laba rugi satu
bulan dengan benar, dan cara termudah membuat tren dua belas bulan adalah
memanggilnya dua belas kali. Itu **tujuh kueri dikali dua belas = 84**.

Angka itu bukan tebakan tentang apa yang lambat. Riwayat rasio pernah
dikirim dengan 149 kueri, dan yang memakainya melaporkannya sebagai lambat
sebelum sempat dipakai. Setelah dijadikan kueri berkelompok, jumlahnya turun
ke 82 dan keluhannya berhenti.

Jadi di sini pengelompokannya dilakukan BASIS DATA: setiap kueri
mengembalikan seluruh bulan sekaligus lewat `GROUP BY tahun, bulan`.
Jumlahnya **tujuh kueri untuk berapa pun bulannya**.

HARGA YANG DIBAYAR, DAN BAGAIMANA DITEBUS

Ada dua penyusun angka yang sama di dua tempat. Kalau yang di sini menyimpang
seujung pun dari `_agregasi`, halaman KPI dan laporan laba rugi akan menyebut
dua laba berbeda untuk bulan yang sama — dan yang melihatnya tidak punya cara
tahu mana yang benar.

Tiga hal menahannya:

  1. Seluruh aturan kategori DIIMPOR dari `laba_rugi_repository`, tidak
     disalin. Pemetaan kategori ke baris laporan cuma ada satu tempat, dan
     memindahkannya di sana ikut memindahkan yang di sini.
  2. Penyaring tiap tabelnya ditulis persis sama dengan laba ruginya —
     termasuk `sales_invoices` yang hanya menghitung faktur DISETUJUI
     (sejak 21 Sep 2026; sama dengan penyebut DSO).
  3. `test/integrasi_kpi_setara_test.py` menjalankan KEDUANYA atas basis data
     yang sama dan menuntut angkanya sama, bulan per bulan.

YANG SENGAJA TIDAK DISUSUN DI SINI

Rincian per kategori. Halaman KPI menampilkan garis besarnya; yang ingin tahu
"beban usaha ini isinya apa" membuka laporan laba rugi, yang memang untuk
itu. Menyusun rincian per bulan di sini berarti menduplikasi bagian yang
paling mungkin menyimpang, demi tampilan yang belum diminta siapa pun.
"""

from datetime import date as d, timedelta
from typing import Any, Dict, List, Tuple

from sqlalchemy import and_, func, or_, select

from models.asset_model import asset_table
from models.expense_model import expenses_table
from models.purchase_model import purchases_table
from models.reimbursement_model import (
    reimbursement_items_table,
    reimbursements_table,
)
from models.salary_slip_model import (
    salary_slips_allowance_table,
    salary_slips_table,
)
from models.sales_invoice_model import sales_invoice_tables
from repository.laba_rugi_repository import (
    GRUP_HPP,
    GRUP_LAIN,
    GRUP_USAHA,
    KATEGORI_DIKECUALIKAN,
    _grup_label,
    _grup_label_pembelian,
)
from utils.database import database
from utils.logger_utils import log_error

#: Batas atas bulan yang boleh diminta sekaligus.
#:
#: Bukan demi kecepatan — jumlah kuerinya tetap tujuh berapa pun bulannya.
#: Ini demi penyusutan, yang dihitung di Python untuk setiap aset dikali
#: setiap bulan; permintaan bertahun-tahun membuat perkalian itu tumbuh tanpa
#: ada yang pernah memintanya.
MAKS_BULAN = 60


def _kunci(tahun: Any, bulan: Any) -> Tuple[int, int]:
    return (int(tahun), int(bulan))


def _bulan_mundur(mundur: int, sampai: d) -> List[Tuple[int, int]]:
    """
    Pasangan (tahun, bulan) dari yang terlama ke `sampai`, kronologis.

    Aritmetika bulan ditulis sendiri, bukan lewat pustaka tanggal: menambah
    "satu bulan" pada 31 Januari tidak punya jawaban yang benar, dan seluruh
    berkas ini hanya butuh pasangan tahun-bulan.
    """
    t, b = sampai.year, sampai.month
    b -= mundur - 1
    while b <= 0:
        b += 12
        t -= 1

    hasil: List[Tuple[int, int]] = []
    for _ in range(mundur):
        hasil.append((t, b))
        b += 1
        if b > 12:
            b = 1
            t += 1
    return hasil


def _akhir_bulan(tahun: int, bulan: int) -> d:
    awal_berikut = (
        d(tahun + 1, 1, 1) if bulan == 12 else d(tahun, bulan + 1, 1)
    )
    return awal_berikut - timedelta(days=1)


# ---------------------------------------------------------------------------
# PAPAN ANTREAN
#
# Berapa banyak dokumen menggantung di tiap tahap, dan yang tertua sudah
# berapa lama.
#
# KENAPA INI TIDAK ADA SEBELUMNYA
#
# `lencana_repository` sudah menjawab "berapa yang menunggu SAYA", dan itu
# yang muncul sebagai angka di menu. Yang tidak dijawab siapa pun: berapa
# LAMA. Sepuluh dokumen yang masuk pagi ini dan sepuluh yang menggantung
# sejak bulan lalu menghasilkan lencana yang sama persis — dan yang kedua
# adalah keadaan yang perlu ditindaklanjuti, bukan sekadar dikerjakan.
#
# Tidak ada satu pun perhitungan umur tunggu di seluruh sistem ini sebelum
# berkas ini. Yang ada hanya umur PIUTANG dan tenggat UTANG, yang menghitung
# uang, bukan antrean.
#
# YANG SENGAJA TIDAK ADA DI SINI: RUPIAH
#
# Papan ini menyebut jumlah dan umur saja. Begitu ia menyebut nilai dokumen,
# isinya menjadi data keuangan dan izinnya harus dinaikkan ke level 4 — dan
# yang paling perlu melihat antrean justru procurement dan engineering, yang
# levelnya di bawah itu. Nilai dokumennya ada di daftarnya masing-masing.
# ---------------------------------------------------------------------------

#: Batas ember umur tunggu, dalam HARI.
#:
#: Bukan 30/60/90 seperti umur piutang. Piutang berumur 30 hari itu biasa;
#: purchase order yang menunggu diperiksa 30 hari berarti pekerjaannya sudah
#: jalan tanpa dokumen, atau berhenti menunggu dokumen. Antrean persetujuan
#: diukur dalam hari kerja, bukan bulan.
#:
#: Batas atas INKLUSIF; ember terakhir menampung sisanya.
EMBER_UMUR = ((2, "0-2"), (7, "3-7"), (14, "8-14"))
EMBER_TERAKHIR = "15+"


def _ember(hari: int) -> str:
    for batas, nama in EMBER_UMUR:
        if hari <= batas:
            return nama
    return EMBER_TERAKHIR


def _kosong() -> Dict[str, int]:
    return {nama: 0 for _, nama in EMBER_UMUR} | {EMBER_TERAKHIR: 0}


async def _antre(kode: str, modul: str, sql: str, nilai: Dict[str, Any]) -> Dict[str, Any]:
    """
    Satu tahap antrean: jumlah, umur tertua, dan sebaran umurnya.

    `sql` harus mengembalikan satu kolom `umur` — umur tunggu tiap dokumen
    dalam hari — satu baris per dokumen. Pengembaran dilakukan di sini, bukan
    di SQL: batas embernya satu tempat (`EMBER_UMUR`), dan delapan pernyataan
    `CASE` yang disalin ke delapan kueri adalah delapan tempat yang harus
    sepakat.

    KEGAGALAN DISEBUT, TIDAK DIJAWAB NOL. Nol berarti "tidak ada yang
    menunggu" — pernyataan yang berbeda, dan yang keliru justru menenangkan.
    """
    try:
        baris = await database.fetch_all(sql, nilai)
        ember = _kosong()
        tertua = 0
        for r in baris:
            umur = max(0, int(r["umur"] or 0))
            ember[_ember(umur)] += 1
            tertua = max(tertua, umur)
        return {
            "kode": kode,
            "modul": modul,
            "jumlah": len(baris),
            "tertuaHari": tertua,
            "ember": ember,
        }
    except Exception as e:  # noqa: BLE001
        log_error(f"Antrean {kode} gagal: {str(e)}")
        return {
            "kode": kode,
            "modul": modul,
            "jumlah": None,
            "tertuaHari": None,
            "ember": _kosong(),
            "gagal": True,
        }


#: Umur tunggu dalam hari, dihitung basis data.
#:
#: `DATE(...)` membungkus kolom waktu supaya dokumen yang masuk sore ini
#: berumur 0, bukan pecahan hari yang dibulatkan ke bawah menjadi 0 kadang
#: dan 1 kadang tergantung jamnya.
_UMUR = "DATEDIFF(CURDATE(), DATE({kolom})) AS umur"


class _Antrean:
    """
    Kueri tiap tahap, disimpan berdampingan supaya dapat dibaca sekaligus.

    Syaratnya DISALIN dari `lencana_repository` dengan sengaja, dan harus
    tetap sama: dua tempat yang menghitung antrean yang sama dengan syarat
    berbeda akan menyebut dua angka, dan yang membacanya tidak punya cara
    tahu mana yang benar. `test/antrean_kpi_test.py` yang memaksanya tetap
    sepakat.

    SATU PERBEDAAN YANG DISENGAJA: papan ini TIDAK mengecualikan dokumen
    buatan si pembaca sendiri, sedangkan lencana mengecualikannya. Keduanya
    menjawab pertanyaan berbeda — lencana "berapa yang dapat saya kerjakan
    sekarang", papan ini "berapa yang tertahan di tahap ini". Karena itu
    angkanya memang boleh berbeda, dan layarnya harus mengatakan begitu.
    """

    PO_PERIKSA = (
        "SELECT " + _UMUR.format(kolom="createdAt") + " FROM purchase_orders "
        "WHERE isDelete = 0 AND isChecked = 0 AND status = 'draft'"
    )
    PO_SETUJUI = (
        "SELECT " + _UMUR.format(kolom="COALESCE(checkedAt, createdAt)")
        + " FROM purchase_orders "
        "WHERE isDelete = 0 AND isChecked = 1 AND isApproved = 0 "
        "AND status = 'draft'"
    )
    REIMBURSEMENT = (
        "SELECT " + _UMUR.format(kolom="createdAt") + " FROM reimbursements "
        "WHERE isDelete = 0 AND isApprove = 0"
    )
    COP_BAP = (
        "SELECT " + _UMUR.format(kolom="createdAt")
        + " FROM certificate_of_payments "
        "WHERE isDelete = 0 AND status <> 'cancelled' AND isBapApproved = 0"
    )
    COP_SETUJUI = (
        "SELECT " + _UMUR.format(kolom="COALESCE(copCreatedAt, createdAt)")
        + " FROM certificate_of_payments "
        "WHERE isDelete = 0 AND status <> 'cancelled' AND isBapApproved = 1 "
        "AND isCopCreated = 1 AND isApproved = 0"
    )
    TENDER = (
        "SELECT " + _UMUR.format(kolom="createdAt") + " FROM tenders "
        "WHERE isDelete = 0 AND status = 'draft'"
    )
    # Dua tahap di bawah TIDAK punya lencana sama sekali — tidak ada apa pun
    # di sistem ini yang memberi tahu bahwa keduanya menggantung. Keduanya
    # menahan uang: yang satu pembayaran yang belum boleh keluar, yang lain
    # tagihan yang belum boleh dikirim.
    PEMBAYARAN = (
        "SELECT " + _UMUR.format(kolom="createdAt") + " FROM payment_outgoing "
        "WHERE isDelete = 0 AND isApprove = 0 "
        "AND (status IS NULL OR status <> 'reject')"
    )
    FAKTUR = (
        "SELECT " + _UMUR.format(kolom="createdAt") + " FROM sales_invoices "
        "WHERE isDelete = 0 AND isApprove = 0"
    )


class KpiRepository:
    @staticmethod
    async def laba_per_bulan(
        mundur: int = 12, sampai: d | None = None
    ) -> Dict[str, Any]:
        """
        Pendapatan, harga pokok, beban, dan laba untuk tiap bulan.

        Tujuh kueri, berapa pun `mundur`-nya.

        Bulan yang TIDAK punya dokumen sama sekali tetap dikembalikan dengan
        nilai nol, bukan dihilangkan. Bulan yang hilang dari deret membuat
        grafiknya menyambung dua bulan yang tidak berurutan, dan penurunan
        yang sebenarnya terbaca sebagai garis datar.
        """
        try:
            mundur = max(1, min(int(mundur or 12), MAKS_BULAN))
            sampai = sampai or d.today()
            bulan_list = _bulan_mundur(mundur, sampai)

            awal = d(bulan_list[0][0], bulan_list[0][1], 1)
            akhir = _akhir_bulan(*bulan_list[-1])

            # Kerangka hasil disiapkan lebih dulu untuk SELURUH bulan.
            ember: Dict[Tuple[int, int], Dict[str, float]] = {
                k: {
                    "pendapatan": 0.0,
                    GRUP_HPP: 0.0,
                    GRUP_USAHA: 0.0,
                    GRUP_LAIN: 0.0,
                }
                for k in bulan_list
            }

            def _tambah(kunci, grup, nilai):
                # Bulan di luar rentang yang diminta diabaikan diam-diam:
                # kueri dibatasi rentangnya, jadi ini hanya penjaga terakhir.
                if kunci in ember:
                    ember[kunci][grup] += nilai

            th = func.extract("year", sales_invoice_tables.c.date)
            bl = func.extract("month", sales_invoice_tables.c.date)
            baris = await database.fetch_all(
                select(
                    th.label("th"),
                    bl.label("bl"),
                    func.coalesce(
                        func.sum(sales_invoice_tables.c.dpp), 0
                    ).label("nilai"),
                )
                .where(
                    and_(
                        sales_invoice_tables.c.isDelete == False,  # noqa: E712
                        sales_invoice_tables.c.isApprove == True,  # noqa: E712
                        sales_invoice_tables.c.date >= awal,
                        sales_invoice_tables.c.date <= akhir,
                    )
                )
                .group_by(th, bl)
            )
            for r in baris:
                k = _kunci(r["th"], r["bl"])
                if k in ember:
                    ember[k]["pendapatan"] += float(r["nilai"] or 0)

            th = func.extract("year", purchases_table.c.date)
            bl = func.extract("month", purchases_table.c.date)
            baris = await database.fetch_all(
                select(
                    th.label("th"),
                    bl.label("bl"),
                    purchases_table.c.purchaseType,
                    func.coalesce(
                        func.sum(
                            purchases_table.c.dpp
                            + purchases_table.c.pbbkb
                            + func.coalesce(purchases_table.c.otherValue, 0)
                        ),
                        0,
                    ).label("nilai"),
                )
                .where(
                    and_(
                        purchases_table.c.isDelete == False,  # noqa: E712
                        purchases_table.c.isInternal == False,  # noqa: E712
                        purchases_table.c.date >= awal,
                        purchases_table.c.date <= akhir,
                    )
                )
                .group_by(th, bl, purchases_table.c.purchaseType)
            )
            for r in baris:
                nilai = float(r["nilai"] or 0)
                if not nilai or str(r["purchaseType"]) in KATEGORI_DIKECUALIKAN:
                    continue
                grup, _ = _grup_label_pembelian(r["purchaseType"])
                _tambah(_kunci(r["th"], r["bl"]), grup, nilai)

            th = func.extract("year", expenses_table.c.date)
            bl = func.extract("month", expenses_table.c.date)
            baris = await database.fetch_all(
                select(
                    th.label("th"),
                    bl.label("bl"),
                    expenses_table.c.purchaseType,
                    func.coalesce(
                        func.sum(
                            expenses_table.c.dpp + expenses_table.c.pbbkb
                        ),
                        0,
                    ).label("nilai"),
                )
                .where(
                    and_(
                        expenses_table.c.isDelete == False,  # noqa: E712
                        expenses_table.c.date >= awal,
                        expenses_table.c.date <= akhir,
                    )
                )
                .group_by(th, bl, expenses_table.c.purchaseType)
            )
            for r in baris:
                nilai = float(r["nilai"] or 0)
                if not nilai or str(r["purchaseType"]) in KATEGORI_DIKECUALIKAN:
                    continue
                grup, _ = _grup_label(r["purchaseType"])
                _tambah(_kunci(r["th"], r["bl"]), grup, nilai)

            th = func.extract("year", reimbursements_table.c.date)
            bl = func.extract("month", reimbursements_table.c.date)
            baris = await database.fetch_all(
                select(
                    th.label("th"),
                    bl.label("bl"),
                    reimbursements_table.c.purchaseType,
                    func.coalesce(
                        func.sum(reimbursement_items_table.c.amount), 0
                    ).label("nilai"),
                )
                .select_from(
                    reimbursements_table.join(
                        reimbursement_items_table,
                        reimbursements_table.c.id
                        == reimbursement_items_table.c.reimbursementID,
                    )
                )
                .where(
                    and_(
                        reimbursements_table.c.isDelete == False,  # noqa: E712
                        reimbursements_table.c.isApprove == True,  # noqa: E712
                        reimbursements_table.c.date >= awal,
                        reimbursements_table.c.date <= akhir,
                    )
                )
                .group_by(th, bl, reimbursements_table.c.purchaseType)
            )
            for r in baris:
                nilai = float(r["nilai"] or 0)
                if not nilai or str(r["purchaseType"]) in KATEGORI_DIKECUALIKAN:
                    continue
                grup, _ = _grup_label_pembelian(r["purchaseType"])
                _tambah(_kunci(r["th"], r["bl"]), grup, nilai)

            # Penyusutan — SATU kueri untuk seluruh aset, sebarannya per bulan
            # dihitung di sini. Aritmetikanya sengaja sama persis dengan
            # `_penyusutan_rentang`: bulan perolehan ikut disusut, berhenti
            # saat habis masa manfaat atau saat dijual.
            aset = await database.fetch_all(
                select(
                    asset_table.c.value,
                    asset_table.c.depreciation,
                    asset_table.c.purchaseDate,
                    asset_table.c.soldDate,
                ).where(asset_table.c.purchaseDate <= akhir)
            )
            for r in aset:
                tahun_manfaat = int(r["depreciation"] or 0)
                nilai = float(r["value"] or 0)
                pd = r["purchaseDate"]
                if tahun_manfaat <= 0 or nilai <= 0 or pd is None:
                    continue
                per_bulan = nilai / (tahun_manfaat * 12)
                mulai_idx = pd.year * 12 + pd.month
                habis_idx = mulai_idx + tahun_manfaat * 12
                sold = r["soldDate"]
                jual_idx = (sold.year * 12 + sold.month) if sold else None
                for (yy, mm) in bulan_list:
                    idx = yy * 12 + mm
                    if idx < mulai_idx or idx >= habis_idx:
                        continue
                    if jual_idx is not None and idx >= jual_idx:
                        continue
                    ember[(yy, mm)][GRUP_USAHA] += per_bulan

            # Gaji — diakui pada PERIODE slip (`month`/`year`), bukan tanggal
            # bayar, sejalan dengan basis akrual laporannya.
            periode = or_(
                *[
                    and_(
                        salary_slips_table.c.year == y,
                        salary_slips_table.c.month == m,
                    )
                    for (y, m) in bulan_list
                ]
            )
            baris = await database.fetch_all(
                select(
                    salary_slips_table.c.year.label("th"),
                    salary_slips_table.c.month.label("bl"),
                    func.coalesce(
                        func.sum(
                            salary_slips_table.c.basicSalary
                            + salary_slips_table.c.transportationAllowanceRate
                            * salary_slips_table.c.transportationAllowanceQuantity
                            + salary_slips_table.c.mealAllowanceRate
                            * salary_slips_table.c.mealAllowanceQuantity
                            + salary_slips_table.c.overtimeRate
                            * salary_slips_table.c.overtimeQuantity
                        ),
                        0,
                    ).label("nilai"),
                )
                .where(
                    and_(
                        salary_slips_table.c.isDelete == False,  # noqa: E712
                        periode,
                    )
                )
                .group_by(
                    salary_slips_table.c.year, salary_slips_table.c.month
                )
            )
            for r in baris:
                _tambah(_kunci(r["th"], r["bl"]), GRUP_USAHA, float(r["nilai"] or 0))

            baris = await database.fetch_all(
                select(
                    salary_slips_table.c.year.label("th"),
                    salary_slips_table.c.month.label("bl"),
                    func.coalesce(
                        func.sum(salary_slips_allowance_table.c.amount), 0
                    ).label("nilai"),
                )
                .select_from(
                    salary_slips_allowance_table.join(
                        salary_slips_table,
                        salary_slips_table.c.id
                        == salary_slips_allowance_table.c.salarySlipID,
                    )
                )
                .where(
                    and_(
                        salary_slips_table.c.isDelete == False,  # noqa: E712
                        periode,
                    )
                )
                .group_by(
                    salary_slips_table.c.year, salary_slips_table.c.month
                )
            )
            for r in baris:
                _tambah(_kunci(r["th"], r["bl"]), GRUP_USAHA, float(r["nilai"] or 0))

            hasil = []
            for (yy, mm) in bulan_list:
                e = ember[(yy, mm)]
                pendapatan = round(e["pendapatan"], 2)
                hpp = round(e[GRUP_HPP], 2)
                usaha = round(e[GRUP_USAHA], 2)
                lain = round(e[GRUP_LAIN], 2)
                laba_kotor = round(pendapatan - hpp, 2)
                laba_usaha = round(laba_kotor - usaha, 2)
                hasil.append(
                    {
                        "tahun": yy,
                        "bulan": mm,
                        "pendapatan": pendapatan,
                        "hpp": hpp,
                        "labaKotor": laba_kotor,
                        "bebanUsaha": usaha,
                        "labaUsaha": laba_usaha,
                        "bebanLain": lain,
                        "labaSebelumPajak": round(laba_usaha - lain, 2),
                    }
                )
            return {"bulan": hasil}
        except Exception as e:  # noqa: BLE001
            log_error(f"Gagal menyusun KPI laba per bulan: {str(e)}")
            # `gagal` DISEBUT, bukan dijawab deret kosong.
            #
            # Deret kosong akan digambar sebagai perusahaan tanpa pendapatan
            # sama sekali — grafik yang rata di nol, dan tidak satu pun galat
            # yang menyebutkan bahwa angkanya memang tidak terbaca.
            return {"bulan": [], "gagal": True}

    @staticmethod
    async def antrean(user: dict, level: int, departemen: set) -> Dict[str, Any]:
        """
        Seluruh tahap yang boleh dilihat pengguna ini, beserta umur tunggunya.

        IZINNYA DIPINJAM, BUKAN DIBUAT BARU. Tiap tahap hanya muncul bila
        penggunanya memang boleh mengerjakan tahap itu, memakai fungsi izin yang
        sama persis dengan tombolnya dan dengan lencananya. Modul baru untuk
        papan ini akan menjadi tempat ketiga yang harus sepakat — dan wilayah
        divisi yang terlewat sudah dua kali membuat modul tak terjangkau siapa
        pun (`audit_log`, `reminder`).

        Tahap yang tidak boleh dilihat TIDAK muncul sebagai nol; ia tidak muncul
        sama sekali. Nol berarti "tidak ada yang menunggu di tahap itu", dan itu
        pernyataan yang berbeda dari "Anda tidak berhak melihatnya".
        """
        from utils.permission import (
            boleh_memeriksa,
            boleh_menyetujui_bap_cop,
            boleh_menyetujui_cop,
            is_allowed,
        )

        tahap: List[Dict[str, Any]] = []

        if boleh_memeriksa(level, departemen):
            tahap.append(
                await _antre(
                    "poPeriksa", "purchase_order", _Antrean.PO_PERIKSA, {}
                )
            )
        if await is_allowed(user, "purchase_order", "approve"):
            tahap.append(
                await _antre(
                    "poSetujui", "purchase_order", _Antrean.PO_SETUJUI, {}
                )
            )
        if await is_allowed(user, "reimbursement", "approve"):
            tahap.append(
                await _antre(
                    "reimbursement", "reimbursement", _Antrean.REIMBURSEMENT, {}
                )
            )
        if boleh_menyetujui_bap_cop(level):
            tahap.append(
                await _antre(
                    "copBap", "certificate_of_payment", _Antrean.COP_BAP, {}
                )
            )
        if boleh_menyetujui_cop(level):
            tahap.append(
                await _antre(
                    "copSetujui",
                    "certificate_of_payment",
                    _Antrean.COP_SETUJUI,
                    {},
                )
            )
        if await is_allowed(user, "tender", "approve"):
            tahap.append(await _antre("tender", "tender", _Antrean.TENDER, {}))
        if await is_allowed(user, "payment_outgoing", "approve"):
            tahap.append(
                await _antre(
                    "pembayaran", "payment_outgoing", _Antrean.PEMBAYARAN, {}
                )
            )
        if await is_allowed(user, "sales_invoice", "approve"):
            tahap.append(
                await _antre("faktur", "sales_invoice", _Antrean.FAKTUR, {})
            )

        return {"tahap": tahap}
