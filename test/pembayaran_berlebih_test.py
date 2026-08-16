"""
Pembayaran yang melebihi sisa tagihan ditolak.

Tanpa penjagaan ini, dokumen yang sudah lunas masih dapat dibayar sekali lagi
— dan uangnya benar-benar keluar. Kesalahannya baru terlihat saat rekonsiliasi
bank, ketika uangnya sudah berpindah dan penagihannya kembali bergantung pada
itikad baik pemasok.

Diperiksa di SERVER. Menyembunyikan tombolnya di layar tidak cukup: muatan
permintaan dapat disusun sendiri oleh siapa pun yang membuka Network tab.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERKAS = os.path.join(AKAR, 'controllers', 'payment_outgoing_controller.py')


def _blok(nama: str) -> str:
    s = open(BERKAS).read()
    i = s.index(f'async def {nama}(')
    j = s.find('\n    @staticmethod', i)
    return s[i:] if j == -1 else s[i:j]


def test_penghitung_sisa_ada():
    s = open(BERKAS).read()
    assert 'async def _sisa_tagihan' in s


def test_sisa_dihitung_dari_yang_disetujui():
    """
    Sama persis dengan cara `isPaid` disimpulkan.

    Bila keduanya memakai dasar yang berbeda, akan ada dokumen yang ditandai
    lunas tetapi masih menerima pembayaran, atau sebaliknya.
    """
    b = _blok('_sisa_tagihan')
    assert 'p.isApprove' in b
    assert 'p.isDelete' in b


def test_pembuatan_menolak_yang_lunas():
    b = _blok('create_payment')
    assert '_sisa_tagihan' in b
    assert 'PAYMENT_LOCKED' in b


def test_pembuatan_menolak_yang_melebihi():
    b = _blok('create_payment')
    assert 'nominal - sisa > 5' in b


def test_toleransi_lima_rupiah():
    """
    Pembulatan pajak menyisakan selisih beberapa rupiah yang bukan kelebihan
    bayar. Angka lima dipakai konsisten dengan perhitungan `isPaid`.
    """
    b = _blok('create_payment')
    assert 'sisa <= 5' in b


def test_dokumen_tak_dikenal_tidak_diblokir():
    """
    Jenis pembayaran yang belum didaftarkan di penghitung mengembalikan
    `None`, dan itu diperlakukan sebagai "tidak dapat diperiksa" — bukan
    ditolak. Menolak yang tidak dapat diperiksa akan memblokir jenis baru
    yang belum sempat ditambahkan.
    """
    b = _blok('create_payment')
    assert 'if sisa is not None:' in b
