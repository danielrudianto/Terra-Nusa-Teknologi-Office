"""
Riwayat rasio: versi BANYAK-TANGGAL harus sama persis dengan versi
satu-tanggal.

KENAPA BERKAS INI ADA

Halaman riwayat dulu memanggil setiap sumber dua belas kali — sekali per
bulan. Untuk sebagian besar sumber itu hanya boros; untuk `total_kas` itu
fatal. Ia memindai VIEW `mutation` lewat kunci yang DIHITUNG
(`CONCAT(date, LPAD(sortorder), LPAD(tiebreaker))`), dan kunci hitung tidak
dapat memakai indeks apa pun: setiap panggilan menyusun ulang seluruh
riwayat transaksi perusahaan, dua kali. Dikali dua belas, halamannya
menggantung.

Perbaikannya mengambil empat sumber SEKALI untuk seluruh bulan lalu menyusun
potretnya di Python. Artinya rumusnya kini ada DUA SALINAN.

Dua salinan yang menyimpang tidak menghasilkan galat apa pun. Yang terjadi:
grafik riwayat menyebut angka yang berbeda dari kartu di kepala halaman —
untuk hari yang SAMA, di layar yang sama — dan yang membacanya tidak punya
cara tahu mana yang berlaku. Berkas ini membandingkan keduanya bidang demi
bidang terhadap basis data sungguhan, karena itu satu-satunya cara
membuktikannya.

Lihat `test/_integrasi.py` untuk cara menjalankannya.
"""

import pytest

from _integrasi import butuh_db, sambungan  # noqa: F401

pytestmark = butuh_db

#: Bidang yang memang BOLEH berbeda bentuknya, bukan nilainya.
DILEWATI = {"error", "sejak"}


def _sama(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        return abs(float(a or 0) - float(b or 0)) < 0.01
    return a == b


@pytest.mark.asyncio
async def test_sumber_batch_sama_dengan_sumber_per_tanggal(sambungan):
    from controllers.finance_status_controller import (
        FinanceStatusController as FS,
    )
    from repository.finance_status_repository import (
        FinanceStatusRepository as R,
    )

    tanggal = FS._titik_bulan(12)

    peta = {
        "aset": await R.aset_per_tanggal(tanggal),
        "pinjaman": await R.pinjaman_per_tanggal(tanggal),
        "arus": await R.arus_per_tanggal(tanggal),
        "kas": await R.kas_per_bulan(tanggal),
    }
    satuan = {
        "aset": R.nilai_buku_aset,
        "pinjaman": R.pinjaman,
        "arus": R.arus_setahun,
        "kas": R.total_kas,
    }

    beda = []
    for t in tanggal:
        k = t.isoformat()
        for nama, fungsi in satuan.items():
            batch = peta[nama][k]
            satu = await fungsi(t)
            for bidang, nilai in batch.items():
                if bidang in DILEWATI:
                    continue
                if not _sama(nilai, satu.get(bidang)):
                    beda.append(
                        f"{k} {nama}.{bidang}: "
                        f"banyak-tanggal={nilai} satu-tanggal={satu.get(bidang)}"
                    )

    assert not beda, (
        "versi banyak-tanggal menyimpang dari versi satu-tanggal — grafik "
        "riwayat akan menyebut angka yang berbeda dari kartu di kepala "
        "halaman, untuk hari yang sama:\n  " + "\n  ".join(beda)
    )


@pytest.mark.asyncio
async def test_kas_per_bulan_menolak_tanggal_tengah_bulan(sambungan):
    """
    Pengelompokan per bulan TIDAK dapat menjawab tanggal tengah bulan.

    Ia akan memberi saldo AKHIR bulan itu — masa depan bagi tanggal yang
    diminta — dan angkanya tetap terlihat wajar. Yang dijaga di sini bukan
    penolakannya melainkan kesadaran akan batasnya: riwayat memakai akhir
    bulan untuk semua titik kecuali yang terakhir, dan yang terakhir memakai
    saldo TERCATAT, bukan fungsi ini.
    """
    from datetime import date as d

    from repository.finance_status_repository import (
        FinanceStatusRepository as R,
    )

    akhir = d(2026, 8, 31)
    tengah = d(2026, 8, 15)
    hasil = await R.kas_per_bulan([akhir, tengah])

    # Keduanya jatuh pada bulan yang sama, jadi keduanya menerima saldo
    # penutup bulan itu. Ini BUKAN bug yang disembunyikan — ini batasan yang
    # dituliskan, supaya pemanggil berikutnya tahu ia tidak boleh mengirim
    # tanggal tengah bulan ke sini.
    assert hasil[akhir.isoformat()]["total"] == hasil[tengah.isoformat()]["total"]
