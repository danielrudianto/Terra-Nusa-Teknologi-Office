"""
Porsi pinjaman yang jatuh tempo dalam 12 bulan — `porsi_lancar()`.

Angka ini masuk ke kewajiban lancar dan karena itu ke quick ratio. Bila
salah, rasio likuiditas menyimpang tanpa galat apa pun. Setiap kasus di
bawah dihitung tangan lebih dulu.

Diverifikasi juga di MariaDB sungguhan (pinjaman ORIX 36 bulan + pinjaman
pribadi): `pinjaman()` dan `pinjaman_per_tanggal()` sama-sama menghasilkan
total 38 jt, lancar 12 jt, tanpa tenor 10 jt.
"""

from datetime import date as d

from repository.finance_status_repository import _tambah_bulan, porsi_lancar

PADA = d(2026, 9, 21)


def test_tanpa_tenor_tidak_diketahui_bukan_nol():
    """Pinjaman pribadi: porsinya tidak diketahui, dan tetap di luar rasio."""
    assert porsi_lancar(10_000_000, 10_000_000, None, None, d(2026, 3, 1), PADA) is None
    assert porsi_lancar(10_000_000, 10_000_000, 0, None, d(2026, 3, 1), PADA) is None


def test_sesuai_jadwal_dua_belas_angsuran():
    # 36 x 1 jt, angsuran pertama 1 Feb; per 21 Sep jatuh 8 jadwal, sisa 28.
    # Sudah bayar 8 jt -> sisa 28 jt. Bukan lancar 16 x 1 jt -> lancar 12 jt.
    assert porsi_lancar(28e6, 36e6, 36, d(2026, 2, 1), d(2026, 1, 5), PADA) == 12e6


def test_tunggakan_ikut_lancar_seluruhnya():
    # Sama, tetapi baru bayar 5 jt: sisa 31 jt, 3 jt di antaranya tunggakan.
    # Bukan lancar tetap 16 jt -> lancar 15 jt (12 ke depan + 3 tertunggak).
    assert porsi_lancar(31e6, 36e6, 36, d(2026, 2, 1), d(2026, 1, 5), PADA) == 15e6


def test_sisa_jadwal_kurang_dari_setahun_seluruhnya_lancar():
    # 12 x 1 jt mulai 1 Mar 2026: per 21 Sep jatuh 7, sisa 5 jadwal.
    assert porsi_lancar(5e6, 12e6, 12, d(2026, 3, 1), d(2026, 2, 1), PADA) == 5e6


def test_lewat_tenor_seluruh_sisa_lancar():
    assert porsi_lancar(2e6, 12e6, 12, d(2025, 1, 1), d(2024, 12, 1), PADA) == 2e6


def test_bayar_di_muka_tidak_negatif():
    # Sisa sudah lebih kecil dari yang "bukan lancar" — lancar dibatasi 0.
    assert porsi_lancar(5e6, 36e6, 36, d(2026, 2, 1), d(2026, 1, 5), PADA) == 0.0


def test_tanpa_tanggal_angsuran_pertama_dianggap_sebulan_sesudah_pinjam():
    a = porsi_lancar(28e6, 36e6, 36, None, d(2026, 1, 1), PADA)
    b = porsi_lancar(28e6, 36e6, 36, d(2026, 2, 1), d(2026, 1, 1), PADA)
    assert a == b


def test_jadwal_tepat_pada_tanggal_acuan_sudah_jatuh_tempo():
    # Angsuran ke-8 jatuh 1 Sep; acuan 1 Sep -> ikut terhitung jatuh tempo.
    a = porsi_lancar(28e6, 36e6, 36, d(2026, 2, 1), None, d(2026, 9, 1))
    assert a == 12e6


def test_sisa_nol_bukan_none():
    assert porsi_lancar(0, 36e6, 36, d(2026, 2, 1), None, PADA) == 0.0


def test_tambah_bulan_akhir_bulan():
    assert _tambah_bulan(d(2026, 1, 31), 1) == d(2026, 2, 28)
    assert _tambah_bulan(d(2028, 1, 31), 1) == d(2028, 2, 29)
    assert _tambah_bulan(d(2026, 11, 30), 3) == d(2027, 2, 28)
    assert _tambah_bulan(d(2026, 12, 15), 1) == d(2027, 1, 15)
