"""
Awalan nomor harus mengikuti dokumen yang benar-benar terbit.

PO-F satu-satunya jenis yang bentuknya bergantung isian: jasa pengujian
menghasilkan SURAT PERINTAH KERJA, pengadaan material menghasilkan PURCHASE
ORDER.

Nomor dan judul yang bertentangan pada satu lembar membuat vendor menerima
dua sebutan berbeda untuk dokumen yang sama — dan yang mengarsipkannya tidak
tahu mana yang benar.

Sudah terjadi: `ujitanah` ditambahkan di layar, tetapi daftar di controller
tidak ikut, sehingga SPK uji tanah bernomor `040-PO-A3EXT-F`.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERKAS = os.path.join(AKAR, 'controllers', 'purchase_order_controller.py')


def test_seluruh_jasa_uji_menghasilkan_spk():
    s = open(BERKAS).read()
    i = s.index('MATERIAL_JASA_UJI = ')
    daftar = s[i:i + 120]
    for jenis in ('ujitekan', 'ujibesi', 'ujitanah'):
        assert jenis in daftar, jenis


def test_daftar_tidak_ditulis_ganda():
    """
    Ditulis di dua tempat, yang satu pasti tertinggal ketika jenis baru
    ditambahkan — dan itu persis yang sudah terjadi.
    """
    s = open(BERKAS).read()
    assert s.count('"ujitekan"') == 1, 'daftar jasa uji ditulis lebih dari sekali'
