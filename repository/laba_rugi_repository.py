"""
Laba rugi konsolidasi — "versi kita".

BUKAN pembukuan resmi dan BUKAN keputusan akuntansi final: angkanya disusun
dari dokumen yang sudah ada di sistem (faktur penjualan, pembelian, beban)
supaya dapat DICOCOKKAN dengan pembukuan akuntan. Tiap baris dapat ditelusuri
balik ke kategori dokumennya, sehingga selisih dengan akuntan mudah dilacak.

Basis AKRUAL: diakui pada TANGGAL DOKUMEN (`date`), bukan tanggal bayar.

Yang TIDAK dihitung sebagai biaya:
  * PPN — dapat dikreditkan, bukan beban;
  * PPh — potongan pajak pihak lain, bukan pengurang biaya di sini.
Karena itu nilai tiap dokumen memakai DPP (+ PBBKB, + nilai lain pembelian),
tanpa PPN maupun PPh.
"""

from datetime import date as d, timedelta

from sqlalchemy import select, func, and_, or_

from utils.database import database
from utils.logger_utils import log_error
from utils.errors import internal_error
from models.expense_model import expenses_table
from models.purchase_model import purchases_table
from models.sales_invoice_model import sales_invoice_tables
from models.asset_model import asset_table
from models.salary_slip_model import (
    salary_slips_table,
    salary_slips_allowance_table,
)
from models.reimbursement_model import (
    reimbursements_table,
    reimbursement_items_table,
)


GRUP_HPP = "hpp"          # Beban Pokok Proyek (harga pokok)
GRUP_USAHA = "beban_usaha"  # Beban Usaha (operasional)
GRUP_LAIN = "beban_lain"    # Pendapatan/Beban Lain (bunga, denda, pajak)


#: Pemetaan kategori beban (`expenses.purchaseType`) -> baris laba-rugi,
#: beserta LABEL yang tampil di laporan.
#:
#: Inilah yang dicocokkan dengan akuntan: bila sebuah kategori menurut mereka
#: masuk baris lain, cukup pindahkan grup-nya di sini — satu tempat.
KATEGORI_BEBAN = {
    # --- Beban proyek langsung -> Harga Pokok ---
    "A": (GRUP_HPP, "Transportasi proyek"),
    "B": (GRUP_HPP, "Sewa alat proyek"),
    "C": (GRUP_HPP, "Bahan bakar proyek"),
    "D": (GRUP_HPP, "Tenaga kerja proyek"),
    "E": (GRUP_HPP, "Koordinasi, konsumsi & akomodasi"),
    "F": (GRUP_HPP, "Material proyek"),
    # 'G' SENGAJA di Beban Usaha, bukan Harga Pokok.
    #
    # Isinya barang utilitas kantor (mis. alat kebersihan untuk gudang yang
    # disewa), bukan biaya yang menempel ke sebuah proyek. Kodenya tetap 'G'
    # supaya data lama tidak perlu diubah; hanya LABEL dan penempatannya di
    # laporan yang berbeda.
    "G": (GRUP_USAHA, "Pembelian barang utilitas kantor"),

    # --- Beban kantor & administrasi -> Beban Usaha ---
    "5.1.1": (GRUP_USAHA, "Pembelian aset"),
    "5.1.2": (GRUP_USAHA, "Perawatan aset"),
    "5.1.3": (GRUP_USAHA, "Sewa dibayar di muka"),
    "5.1.4": (GRUP_USAHA, "Beban karyawan"),
    "5.1.5": (GRUP_USAHA, "Logistik"),
    "5.1.6": (GRUP_USAHA, "Penanganan dokumen & ATK"),
    "5.1.7": (GRUP_USAHA, "Utilitas (listrik, air, dll)"),
    "5.1.9": (GRUP_USAHA, "Biaya administrasi"),
    "5.1.11": (GRUP_USAHA, "Pembulatan"),
    "5.1.12": (GRUP_USAHA, "Perangkat lunak"),
    "5.1.14": (GRUP_USAHA, "Sosial & kemasyarakatan"),
    "6.3.1": (GRUP_USAHA, "Iklan"),
    "6.3.2": (GRUP_USAHA, "Merchandise promosi"),
    "6.3.3": (GRUP_USAHA, "Media sosial"),
    "6.4.1": (GRUP_USAHA, "Legal (akta, SBU)"),
    "6.4.2": (GRUP_USAHA, "Asuransi"),
    "6.5.1": (GRUP_USAHA, "Rekrutmen"),
    "6.5.2": (GRUP_USAHA, "Pelatihan"),
    "6.5.3": (GRUP_USAHA, "Kesehatan"),

    # --- Bunga, denda, pajak -> Beban/Pendapatan Lain ---
    "5.1.10": (GRUP_LAIN, "Bunga"),
    "5.1.13": (GRUP_LAIN, "Denda"),
    # 5.1.8.1 (PPN) SENGAJA tidak di sini — lihat KATEGORI_DIKECUALIKAN.
    "5.1.8.2": (GRUP_LAIN, "Pajak — PPh 23 & 4(2)"),
    "5.1.8.3": (GRUP_LAIN, "Pajak — PPh 21"),
    "5.1.8.4": (GRUP_LAIN, "Pajak — SPT Tahunan"),
    "5.1.8.5": (GRUP_LAIN, "Pajak — Jasa lapor SPT"),
    "5.1.8.6": (GRUP_LAIN, "Pajak — Denda"),
    "5.1.8.7": (GRUP_LAIN, "Pajak atas bunga"),
}


#: Kategori beban yang SENGAJA tidak dihitung sebagai biaya di laba-rugi ini,
#: karena sudah tercermin di tempat lain — memasukkannya berarti menghitung
#: dua kali.
#:
#:  * 5.1.8.1 PPN — laporan memakai DPP di semua baris dan mengecualikan PPN
#:    (dapat dikreditkan). Setoran PPN adalah selisih pajak keluaran-masukan
#:    yang dititipkan ke negara, bukan pengurang laba.
#:  * 5.1.8.3 PPh 21 — sudah termasuk di dalam gaji BRUTO yang dihitung dari
#:    slip gaji. Setorannya bukan biaya tambahan, hanya bagian bruto yang
#:    dipotong dari karyawan lalu disetorkan.
#:  * 5.1.1 Pembelian aset — BUKAN biaya: asetnya tidak hilang, hanya berpindah
#:    menjadi aktiva tetap di neraca. Yang masuk laba rugi hanyalah
#:    PENYUSUTANNYA (dihitung dari daftar aset). Membebankannya penuh sekaligus
#:    berarti menghitung dua kali — sekali saat beli, sekali lewat penyusutan.
KATEGORI_DIKECUALIKAN = {"5.1.8.1", "5.1.8.3", "5.1.1"}


def _grup_label(kode):
    """
    Grup & label sebuah kategori. Yang tak dikenal masuk Beban Usaha dengan
    kodenya sebagai label — lebih baik terlihat sebagai baris tak terpetakan
    daripada diam-diam hilang dari total.
    """
    return KATEGORI_BEBAN.get(str(kode), (GRUP_USAHA, f"Lainnya ({kode})"))


#: Pemetaan `purchases.purchaseType` untuk pembelian PROYEK -> Harga Pokok.
#:
#: Kode ini sama dengan kartu "project" pada pembuatan Purchase Order. Tujuannya
#: memecah Harga Pokok per jenis, bukan melebur semua pembelian jadi satu baris
#: "material & jasa".
#:
#: Catatan 'G': pada PEMBELIAN, G = perlengkapan & peralatan proyek (palu,
#: cangkul, sepatu — kartu "Equipments"). Ini BEDA dari 'G' pada BEBAN kantor
#: (`KATEGORI_BEBAN`), yang bermakna barang utilitas kantor. Keduanya memang
#: dokumen berbeda, jadi kodenya boleh bermakna beda sesuai sumbernya.
KATEGORI_PEMBELIAN_PROYEK = {
    "A": "Transportasi proyek",
    "B": "Sewa alat proyek",
    "C": "Bahan bakar proyek",
    "D": "Tenaga kerja proyek",
    "E": "Koordinasi, konsumsi & akomodasi",
    "F": "Material proyek",
    "G": "Perlengkapan & peralatan proyek",
    "H": "Pekerjaan subkontrak",
}


def _grup_label_pembelian(kode):
    """
    Grup & label untuk `purchases.purchaseType`.

    Pembelian proyek (A–H) masuk Harga Pokok dengan labelnya sendiri; pembelian
    kantor (kode 5.1.x / 6.x) mengikuti pemetaan beban `KATEGORI_BEBAN` agar
    jatuh ke Beban Usaha, bukan Harga Pokok.
    """
    k = str(kode)
    if k in KATEGORI_PEMBELIAN_PROYEK:
        return GRUP_HPP, KATEGORI_PEMBELIAN_PROYEK[k]
    # Subkontrak dicatat sebagai H1/H2 di data (berkualifikasi / tidak
    # berkualifikasi — beda tarif PPh), bukan "H" polos. Semuanya tetap
    # subkontrak PROYEK, jadi cocokkan awalan 'H' agar tidak jatuh ke
    # "Lainnya" di Beban Usaha.
    if k.upper().startswith("H"):
        return GRUP_HPP, "Pekerjaan subkontrak"
    return _grup_label(kode)


def _bulan_dalam_rentang(a: d, b: d):
    """
    Daftar (tahun, bulan) yang tercakup rentang [a, b].

    `a` diasumsikan jatuh pada awal bulan (pemakaiannya di laba-rugi selalu
    tanggal 1). Dipakai penyusutan, yang dihitung PER BULAN, bukan sekadar
    dijumlah atas rentang tanggal seperti dokumen biasa.
    """
    hasil = []
    y, m = a.year, a.month
    while d(y, m, 1) <= b:
        hasil.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return hasil


async def _penyusutan_rentang(a: d, b: d) -> float:
    """
    Penyusutan garis lurus seluruh aset tetap untuk bulan-bulan dalam [a, b].

    Metode: nilai perolehan dibagi rata sepanjang masa manfaat (kolom
    `depreciation`, dalam TAHUN) x 12 bulan — tanpa nilai sisa, garis lurus
    ke nol, sejalan dengan penyusutan fiskal. Penyusutan DIMULAI pada bulan
    perolehan dan BERHENTI saat aset sudah habis disusutkan atau sudah dijual.

    Aset dengan masa manfaat 0 (mis. tanah) tidak disusutkan.

    CATATAN penting untuk pencocokan dengan akuntan: bila pembelian aset juga
    sudah dicatat sebagai beban langsung (kategori 5.1.1 "Pembelian aset"),
    memasukkan penyusutan di sini berpotensi menghitung dua kali. Baris ini
    sengaja terpisah dan berlabel jelas supaya selisihnya mudah ditelusuri.
    """
    rows = await database.fetch_all(
        select(
            asset_table.c.value,
            asset_table.c.depreciation,
            asset_table.c.purchaseDate,
            asset_table.c.soldDate,
        ).where(asset_table.c.purchaseDate <= b)
    )
    if not rows:
        return 0.0

    bulan_list = _bulan_dalam_rentang(a, b)
    total = 0.0
    for r in rows:
        tahun_manfaat = int(r["depreciation"] or 0)
        nilai = float(r["value"] or 0)
        if tahun_manfaat <= 0 or nilai <= 0:
            continue
        pd = r["purchaseDate"]
        if pd is None:
            continue
        per_bulan = nilai / (tahun_manfaat * 12)
        # Indeks bulan absolut (tahun*12 + bulan) agar perbandingannya ringkas.
        mulai_idx = pd.year * 12 + pd.month            # bulan perolehan (ikut disusut)
        habis_idx = mulai_idx + tahun_manfaat * 12     # bulan pertama TANPA penyusutan
        sold = r["soldDate"]
        jual_idx = (sold.year * 12 + sold.month) if sold else None
        for (yy, mm) in bulan_list:
            idx = yy * 12 + mm
            if idx < mulai_idx or idx >= habis_idx:
                continue
            if jual_idx is not None and idx >= jual_idx:
                continue
            total += per_bulan
    return round(total, 2)


async def _gaji_rentang(a: d, b: d) -> float:
    """
    Total beban gaji untuk bulan-bulan dalam [a, b], dari slip gaji.

    Diakui per PERIODE slip (`month`/`year`), bukan tanggal bayar — sejalan
    dengan basis akrual laporan ini. Gaji disimpan di tabelnya sendiri
    (`salary_slips`), bukan sebagai dokumen beban, sehingga tanpa perhitungan
    ini gaji sama sekali tak muncul di laba rugi.

    Beban = gaji BRUTO yang ditanggung perusahaan: gaji pokok + tunjangan
    transport + tunjangan makan + lembur + tunjangan lain. Potongan (PPh 21,
    BPJS karyawan, dsb) TIDAK dikurangkan — itu bagian dari bruto yang dipotong
    dari karyawan lalu disetorkan, bukan pengurang biaya perusahaan.
    """
    pasangan = _bulan_dalam_rentang(a, b)  # [(tahun, bulan), ...]
    if not pasangan:
        return 0.0
    # OR dari pasangan (tahun, bulan) — sengaja BUKAN tuple_().in_(): IN
    # komposit tidak selalu ter-bind benar di driver async `databases` dan bisa
    # diam-diam tidak cocok apa pun (gaji tampak 0 tanpa error). Bentuk OR ini
    # portabel dan pasti jalan.
    periode = or_(
        *[
            and_(
                salary_slips_table.c.year == y,
                salary_slips_table.c.month == m,
            )
            for (y, m) in pasangan
        ]
    )

    # Komponen tetap pada baris slip.
    pokok = await database.fetch_val(
        select(
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
            )
        ).where(
            and_(
                salary_slips_table.c.isDelete == False,  # noqa: E712
                periode,
            )
        )
    )

    # Tunjangan tambahan (tabel terpisah), dijumlahkan untuk slip pada periode
    # yang sama dan belum dihapus.
    tunjangan = await database.fetch_val(
        select(func.coalesce(func.sum(salary_slips_allowance_table.c.amount), 0))
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
    )

    return round(float(pokok or 0) + float(tunjangan or 0), 2)


async def _agregasi(a: d, b: d) -> dict:
    """Susun satu laba-rugi untuk rentang tanggal [a, b] (inklusif)."""

    # Pendapatan usaha — DPP faktur penjualan yang belum dihapus.
    pendapatan = await database.fetch_val(
        select(func.coalesce(func.sum(sales_invoice_tables.c.dpp), 0)).where(
            and_(
                sales_invoice_tables.c.isDelete == False,  # noqa: E712
                sales_invoice_tables.c.date >= a,
                sales_invoice_tables.c.date <= b,
            )
        )
    )

    # Akumulasi per grup, DIGABUNG berdasarkan label: pembelian dan beban bisa
    # menyumbang ke label yang sama (mis. "Material proyek" dari pembelian F
    # dan beban F), dan pembaca mengharapkan satu baris, bukan dua.
    hpp_map: dict = {}
    usaha_map: dict = {}
    lain_map: dict = {}

    def _tambah(grup, label, nilai):
        m = {GRUP_HPP: hpp_map, GRUP_USAHA: usaha_map, GRUP_LAIN: lain_map}[grup]
        m[label] = m.get(label, 0.0) + nilai

    # Pembelian, DIPECAH per purchaseType. `isInternal` dikecualikan agar mutasi
    # internal tidak terhitung sebagai biaya. Nilai memakai DPP + PBBKB (pajak
    # BBM, hangus jadi biaya) + nilai lain — tanpa PPN.
    baris_pembelian = await database.fetch_all(
        select(
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
                purchases_table.c.date >= a,
                purchases_table.c.date <= b,
            )
        )
        .group_by(purchases_table.c.purchaseType)
    )
    for r in baris_pembelian:
        nilai = float(r["nilai"] or 0)
        if nilai == 0:
            continue
        # Pembelian aset (5.1.1) dsb. dikecualikan — dikapitalisasi, bukan
        # dibebankan. Diperiksa di SINI juga, bukan hanya di loop beban:
        # pembelian aset masuk lewat Purchase Order bertipe 5.1.1.
        if str(r["purchaseType"]) in KATEGORI_DIKECUALIKAN:
            continue
        grup, label = _grup_label_pembelian(r["purchaseType"])
        _tambah(grup, label, nilai)

    # Beban, dijumlahkan per kategori.
    rows = await database.fetch_all(
        select(
            expenses_table.c.purchaseType,
            func.coalesce(
                func.sum(expenses_table.c.dpp + expenses_table.c.pbbkb), 0
            ).label("nilai"),
        )
        .where(
            and_(
                expenses_table.c.isDelete == False,  # noqa: E712
                expenses_table.c.date >= a,
                expenses_table.c.date <= b,
            )
        )
        .group_by(expenses_table.c.purchaseType)
    )
    for r in rows:
        nilai = float(r["nilai"] or 0)
        if nilai == 0:
            continue
        # PPN & PPh 21 sengaja tidak dihitung — lihat KATEGORI_DIKECUALIKAN.
        if str(r["purchaseType"]) in KATEGORI_DIKECUALIKAN:
            continue
        grup, label = _grup_label(r["purchaseType"])
        _tambah(grup, label, nilai)

    # Reimbursement — pengeluaran karyawan yang diganti perusahaan (mis.
    # transport, konsumsi). Tabel tersendiri, tidak masuk `expenses` maupun
    # `purchases`, jadi tanpa ini biayanya hilang dari laba rugi. Nilainya =
    # jumlah item; dirouting per `purchaseType` seperti pembelian (proyek ->
    # HPP, kantor -> Beban Usaha). HANYA yang sudah di-approve (biaya yang
    # benar-benar diakui), belum dihapus.
    baris_reimburse = await database.fetch_all(
        select(
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
                reimbursements_table.c.date >= a,
                reimbursements_table.c.date <= b,
            )
        )
        .group_by(reimbursements_table.c.purchaseType)
    )
    for r in baris_reimburse:
        nilai = float(r["nilai"] or 0)
        if nilai == 0:
            continue
        if str(r["purchaseType"]) in KATEGORI_DIKECUALIKAN:
            continue
        grup, label = _grup_label_pembelian(r["purchaseType"])
        _tambah(grup, label, nilai)

    # Penyusutan aset tetap — beban non-kas, dari daftar aset (bukan dokumen
    # beban), ditambahkan ke Beban Usaha.
    penyusutan = await _penyusutan_rentang(a, b)
    if penyusutan:
        _tambah(GRUP_USAHA, "Penyusutan aset tetap", penyusutan)

    # Beban gaji — dari slip gaji (tabel tersendiri), juga Beban Usaha.
    gaji = await _gaji_rentang(a, b)
    if gaji:
        _tambah(GRUP_USAHA, "Beban gaji", gaji)

    def _rincian(m):
        # label dipakai sekaligus sebagai `kategori` (kunci penggabungan di
        # layar) — unik dalam satu grup, dan stabil antara bulan & YTD.
        return sorted(
            [
                {"kategori": lbl, "label": lbl, "nilai": round(v, 2)}
                for lbl, v in m.items()
                if v
            ],
            key=lambda x: x["nilai"],
            reverse=True,
        )

    # Rincian diurutkan dari yang terbesar — yang paling menentukan di atas.
    hpp_rinci = _rincian(hpp_map)
    usaha_rinci = _rincian(usaha_map)
    lain_rinci = _rincian(lain_map)

    pendapatan = float(pendapatan or 0)
    hpp_total = round(sum(x["nilai"] for x in hpp_rinci), 2)
    usaha_total = round(sum(x["nilai"] for x in usaha_rinci), 2)
    lain_total = round(sum(x["nilai"] for x in lain_rinci), 2)

    laba_kotor = round(pendapatan - hpp_total, 2)
    laba_usaha = round(laba_kotor - usaha_total, 2)
    laba_sebelum_pajak = round(laba_usaha - lain_total, 2)

    return {
        "pendapatan": round(pendapatan, 2),
        "hpp": {"total": hpp_total, "rincian": hpp_rinci},
        "labaKotor": laba_kotor,
        "bebanUsaha": {"total": usaha_total, "rincian": usaha_rinci},
        "labaUsaha": laba_usaha,
        "bebanLain": {"total": lain_total, "rincian": lain_rinci},
        "labaSebelumPajak": laba_sebelum_pajak,
    }


class LabaRugiRepository:
    """Laba rugi konsolidasi: bulan berjalan + akumulasi tahun berjalan."""

    @staticmethod
    async def laba_rugi(month: int, year: int) -> dict:
        try:
            awal_bulan = d(year, month, 1)
            # Hari terakhir bulan = sehari sebelum tanggal 1 bulan berikutnya.
            awal_bulan_berikut = (
                d(year + 1, 1, 1) if month == 12 else d(year, month + 1, 1)
            )
            akhir_bulan = awal_bulan_berikut - timedelta(days=1)
            awal_tahun = d(year, 1, 1)

            bulan = await _agregasi(awal_bulan, akhir_bulan)
            ytd = await _agregasi(awal_tahun, akhir_bulan)

            return {
                "month": month,
                "year": year,
                "bulan": bulan,
                "ytd": ytd,
            }
        except Exception as e:
            log_error(f"Gagal menyusun laba rugi: {str(e)}")
            return internal_error()
