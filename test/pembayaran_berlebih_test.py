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
    assert 'nominal - sisa > TOLERANSI_RUPIAH' in b


def test_toleransi_lima_rupiah():
    """
    Pembulatan pajak menyisakan selisih beberapa rupiah yang bukan kelebihan
    bayar. Angka lima dipakai konsisten dengan perhitungan `isPaid`.
    """
    s = open(BERKAS).read()
    assert 'TOLERANSI_RUPIAH = 5' in s


def test_pintu_ditutup_pada_satu_sen_bukan_lima_rupiah():
    """
    Yang benar-benar tidak dapat dibayar hanya sisa yang sudah NOL.

    Ambang lima rupiah di sini merugikan dua arah. Dokumen yang nilainya
    SENDIRI di bawah lima rupiah langsung dinyatakan lunas dan tidak pernah
    dapat dibayar — itu yang terjadi pada beban Rp 0,11, yang slipnya ditolak
    dengan pesan "terjadi kesalahan di server". Dan sisa di bawah lima rupiah
    pada dokumen besar pun ikut tertutup — padahal justru sisa itulah yang
    dicatat sebagai pembayaran pembulatan, bernilai di bawah satu rupiah.
    """
    b = _blok('create_payment')
    assert 'sisa <= TOLERANSI_LUNAS' in b, (
        'penjaga "sudah lunas" harus memakai ambang satu sen, bukan lima '
        'rupiah — pembayaran pembulatan berada tepat di antara keduanya'
    )


def test_tiga_lapisan_keputusan_lunas():
    """
    Selisih kecil DITANYAKAN, tidak diputuskan sendiri.

    Ambang lima rupiah dibuat untuk menyerap pembulatan pajak, dan ia perlu.
    Tetapi dipakai sebagai keputusan otomatis, ia juga menelan selisih
    pembulatan antar-pembukuan yang di sini justru dicatat sebagai pembayaran
    tersendiri — dan begitu dokumennya bertanda lunas, pembayaran itu tidak
    pernah sempat dibuat.
    """
    s = open(BERKAS).read()
    assert 'def putuskan_lunas(' in s
    assert 'TOLERANSI_LUNAS = 0.01' in s

    i = s.index('def putuskan_lunas(')
    b = s[i:s.index('\n\ndef ', i + 1)]
    assert 'butuh_konfirmasi' in b
    assert 'TOLERANSI_RUPIAH' in b


def test_sisa_tagihan_melaporkan_yang_sudah_dibayar():
    """
    Tanpa angka itu, "tersisa dua rupiah karena pembulatan" tidak dapat
    dibedakan dari "dokumen ini memang bernilai dua rupiah".
    """
    b = _blok('_sisa_tagihan')
    assert '"dibayar"' in b
    assert '"sisa"' in b


def test_dokumen_tak_dikenal_tidak_diblokir():
    """
    Jenis pembayaran yang belum didaftarkan di penghitung mengembalikan
    `None`, dan itu diperlakukan sebagai "tidak dapat diperiksa" — bukan
    ditolak. Menolak yang tidak dapat diperiksa akan memblokir jenis baru
    yang belum sempat ditambahkan.
    """
    b = _blok('create_payment')
    assert 'if tagihan is not None:' in b
