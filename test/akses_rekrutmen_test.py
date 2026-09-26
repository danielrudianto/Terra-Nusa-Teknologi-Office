"""
Batas akses modul rekrutmen.

Isinya data pribadi orang yang bahkan belum menjadi karyawan — alamat,
tanggal lahir — dan jawaban yang menentukan diterima atau tidaknya. Berkas
yang diunggah memuat karya yang belum tentu ingin dilihat orang lain.

Karena itu aturannya sama dengan slip gaji: HRD atau pemilik, dan tidak
terbuka hanya karena levelnya tinggi.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODUL = 'hr_recruitment'


def test_terdaftar_di_matriks():
    from constants.permission_matrix import MATRIX
    assert MODUL in MATRIX


def test_wilayah_mutlak():
    """
    Tanpa ini, seorang General Manager membaca jawaban seluruh pelamar tanpa
    seorang pun pernah memutuskan bahwa ia boleh.
    """
    from utils.permission import MODUL_WILAYAH_MUTLAK
    assert MODUL in MODUL_WILAYAH_MUTLAK


def test_hanya_divisi_hrd():
    from constants.department_modules import DEPARTMENT_MODULES
    pemilik = [k for k, v in DEPARTMENT_MODULES.items() if MODUL in v]
    assert pemilik == ['hrd'], pemilik


def test_level_tinggi_tanpa_hrd_ditolak():
    """
    Level 4 di divisi lain, dan level 4 tanpa divisi sama sekali, keduanya
    ditolak. Yang membukanya harus HRD — atau pemilik.
    """
    from constants.department_modules import modules_for
    from utils.permission import MODUL_WILAYAH_MUTLAK

    def boleh(level, divisi):
        if level < 5 and MODUL in MODUL_WILAYAH_MUTLAK:
            if not divisi or MODUL not in modules_for(divisi):
                return False
        return level >= 3

    assert boleh(5, set())            # pemilik
    assert boleh(3, {'hrd'})          # HRD
    assert not boleh(4, {'fat'})      # divisi lain
    assert not boleh(4, set())        # GM tanpa divisi
    assert not boleh(3, {'procurement'})
    assert not boleh(2, {'hrd'})      # level di bawah batas baca


def test_menghapus_hanya_pemilik():
    """
    Menghapus pelamar berarti menghapus jawaban dan penilaiannya sekaligus —
    keputusan yang tidak dapat ditarik kembali.
    """
    from constants.permission_matrix import MATRIX
    _, _, _, hapus, _ = MATRIX[MODUL]
    assert hapus == 5
