"""
KPI per bulan harus menyebut angka YANG SAMA dengan laporan laba rugi.

KENAPA PENGUJIAN INI ADA

`KpiRepository.laba_per_bulan` menyusun laba rugi sendiri, dalam tujuh kueri
berkelompok, alih-alih memanggil `LabaRugiRepository.laba_rugi` dua belas
kali (yang berharga 168 kueri — diukur, bukan ditaksir).

Harganya: ada dua penyusun angka yang sama. Kalau yang satu menyimpang
seujung pun, halaman KPI dan laporan laba rugi akan menyebut dua laba
berbeda untuk bulan yang sama, dan tidak ada galat apa pun yang menyebutkan
mana yang benar — yang melihatnya hanya kehilangan kepercayaan pada
keduanya.

Kelas kekeliruan yang dijaga di sini bukan hipotetis. Saat ditulis, sabotase
berikut SEMUA lolos uji statis dan build bersih, dan SEMUA tertangkap di
sini:

    saringan `isInternal` dicopot ................ 16 selisih
    kategori 5.1.1 / 5.1.8.x ikut dibebankan ..... 12 selisih
    `isApprove` reimbursement dicopot ............ 16 selisih
    `pbbkb` hilang dari beban .................... 20 selisih
    aset yang sudah dijual tetap disusutkan ......  6 selisih
    tunjangan tambahan tidak dijumlah ............ 12 selisih
    faktur terhapus ikut dihitung ................ 16 selisih

CARA MENJALANKAN

    TEST_DATABASE_URL="mysql://pengguna:sandi@localhost/tnt_restore_test" \\
        ./env/bin/python -m pytest test/integrasi_kpi_setara_test.py -q

Tanpa `TEST_DATABASE_URL` seluruh berkas ini dilewati — lihat `_integrasi.py`.

YANG DIBANDINGKAN, DAN YANG TIDAK

Dibandingkan: pendapatan, harga pokok, laba kotor, beban usaha, laba usaha,
beban lain, laba sebelum pajak — untuk TIAP bulan.

Tidak dibandingkan: rincian per kategori, karena `laba_per_bulan` memang
tidak menyusunnya. Itu keputusan yang disengaja dan dijelaskan di kepala
`repository/kpi_repository.py`.
"""

from datetime import date as d

import pytest

from _integrasi import butuh_db  # noqa: F401

pytestmark = butuh_db

#: Berapa bulan ke belakang yang diperiksa.
#:
#: Enam, bukan dua belas: yang diuji KESETARAAN RUMUSNYA, dan rumus yang sama
#: untuk enam bulan adalah rumus yang sama untuk dua belas. Tiap bulan
#: tambahan berharga empat belas kueri pada sisi pembandingnya.
BULAN_DIPERIKSA = 6

#: Bidang yang harus sama persis. Disebut satu per satu, bukan dibandingkan
#: sebagai dict utuh: bidang baru di salah satu sisi tidak boleh membuat
#: pengujian ini merah tanpa ada angka yang benar-benar berbeda.
BIDANG = (
    "pendapatan",
    "hpp",
    "labaKotor",
    "bebanUsaha",
    "labaUsaha",
    "bebanLain",
    "labaSebelumPajak",
)

#: Selisih yang masih diterima, dalam rupiah.
#:
#: Nol akan salah: kedua sisi membulatkan ke dua desimal pada titik yang
#: berbeda — laba rugi membulatkan tiap baris rincian lalu menjumlahkannya,
#: KPI menjumlahkan lalu membulatkan. Selisih yang mungkin karena itu
#: sebesar pecahan sen, bukan rupiah.
#:
#: Satu rupiah juga cukup ketat: seluruh sabotase yang dicatat di atas
#: menghasilkan selisih puluhan ribu sampai jutaan.
TOLERANSI = 1.0


def _ratakan(bagian: dict) -> dict:
    """`hpp`/`bebanUsaha`/`bebanLain` di laba rugi berupa {total, rincian}."""
    rata = dict(bagian)
    for k in ("hpp", "bebanUsaha", "bebanLain"):
        nilai = bagian.get(k)
        if isinstance(nilai, dict):
            rata[k] = nilai.get("total", 0)
    return rata


@pytest.mark.asyncio
async def test_kpi_per_bulan_sama_dengan_laba_rugi():
    from repository.kpi_repository import KpiRepository
    from repository.laba_rugi_repository import LabaRugiRepository
    from utils.database import database

    sudah_tersambung = database.is_connected
    if not sudah_tersambung:
        await database.connect()
    try:
        hari_ini = d.today()
        kpi = await KpiRepository.laba_per_bulan(
            BULAN_DIPERIKSA, sampai=hari_ini
        )
        assert not kpi.get("gagal"), (
            "KPI menjawab `gagal` — periksa lognya; membandingkan deret "
            "kosong dengan laba rugi akan lulus tanpa menguji apa pun"
        )
        deret = kpi["bulan"]
        assert len(deret) == BULAN_DIPERIKSA, (
            f"diminta {BULAN_DIPERIKSA} bulan, dijawab {len(deret)} — bulan "
            f"tanpa dokumen harus tetap ada sebagai nol, bukan dihilangkan"
        )

        selisih = []
        ada_angka = False
        for titik in deret:
            y, m = titik["tahun"], titik["bulan"]
            lr = await LabaRugiRepository.laba_rugi(m, y)
            assert isinstance(lr, dict) and "error" not in lr, (
                f"laba rugi {y}-{m:02d} gagal: {lr}"
            )
            acuan = _ratakan(lr["bulan"])

            for bidang in BIDANG:
                a = round(float(acuan.get(bidang) or 0), 2)
                b = round(float(titik.get(bidang) or 0), 2)
                if a:
                    ada_angka = True
                if abs(a - b) > TOLERANSI:
                    selisih.append(
                        f"{y}-{m:02d} {bidang}: laba rugi {a:,.2f} "
                        f"vs KPI {b:,.2f} (selisih {a - b:,.2f})"
                    )

        assert not selisih, (
            "KPI dan laporan laba rugi menyebut angka berbeda untuk bulan "
            "yang sama:\n  " + "\n  ".join(selisih)
        )

        # PENJAGA ATAS PENGUJIAN INI SENDIRI.
        #
        # Basis data uji yang kosong membuat seluruh perbandingan di atas
        # membandingkan nol dengan nol — hijau, dan tidak menguji apa pun.
        # Lebih baik berkas ini menyebut dirinya tidak berguna daripada
        # diam-diam menjadi hiasan.
        assert ada_angka, (
            "seluruh angka acuan nol — basis data ujinya tidak memuat "
            "dokumen pada rentang yang diperiksa, jadi kesetaraannya tidak "
            "benar-benar teruji"
        )
    finally:
        if not sudah_tersambung:
            await database.disconnect()


@pytest.mark.asyncio
async def test_jumlah_kueri_tidak_tumbuh_mengikuti_bulan():
    """
    Tujuh kueri untuk berapa pun bulannya.

    Ini SEBAB berkas `kpi_repository.py` ada sama sekali. Bila suatu saat
    seseorang menyederhanakannya menjadi pemanggilan `laba_rugi` per bulan,
    angkanya akan tetap benar dan pengujian di atas tetap hijau — yang
    hilang hanya kecepatannya, diam-diam, sampai ada yang mengeluh lagi.
    """
    from repository.kpi_repository import KpiRepository
    from utils.database import database
    from utils.db_ukur import mulai_ukur

    sudah_tersambung = database.is_connected
    if not sudah_tersambung:
        await database.connect()
    try:
        hari_ini = d.today()

        wadah_pendek = mulai_ukur()
        await KpiRepository.laba_per_bulan(3, sampai=hari_ini)
        pendek = wadah_pendek["n"]

        wadah_panjang = mulai_ukur()
        await KpiRepository.laba_per_bulan(24, sampai=hari_ini)
        panjang = wadah_panjang["n"]

        assert pendek == panjang, (
            f"3 bulan memakai {pendek} kueri, 24 bulan memakai {panjang} — "
            f"jumlahnya tumbuh mengikuti bulan, jadi pengelompokannya sudah "
            f"tidak dilakukan basis data"
        )
        assert panjang <= 10, (
            f"{panjang} kueri untuk satu permintaan; seharusnya tujuh"
        )
    finally:
        if not sudah_tersambung:
            await database.disconnect()
