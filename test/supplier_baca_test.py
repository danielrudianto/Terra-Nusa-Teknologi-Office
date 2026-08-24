"""
Membaca pemasok tidak boleh tunduk pada aturan PENGISIAN.

`SupplierBase` menuntut telepon 10–20 angka dan NPWP persis 16 digit. Aturan
itu tepat ketika data baru diisi, tetapi salah bila dipakai membaca: basis
data memuat pemasok yang dimasukkan sebelum aturannya ada, dan sebagian
memang tidak punya NPWP berbentuk itu.

Menolaknya saat membaca membuat SELURUH permintaan gagal dengan 500 yang tidak
menyebut sebabnya — purchase order yang pemasoknya begitu tidak dapat dibuka
sama sekali.

Sudah terjadi pada PO 225.
"""

import pytest

from schemas.supplier_schema import SupplierCreate, SupplierResponse


LAMA = dict(
    id=1,
    name='PT Contoh',
    address='Jl. Contoh No. 1',
    city='Bekasi',
    province='Jawa Barat',
    phoneNumber='021-888',
    npwp='074411528801400',
    email='bukan-email',
    itemsSold='beton',
    serviceArea='Jabodetabek',
)


def test_data_lama_tetap_terbaca():
    r = SupplierResponse(**LAMA)
    assert r.phoneNumber == '021-888'
    assert r.npwp == '074411528801400'


def test_telepon_kosong_terbaca():
    """Sebagian pemasok lama tidak punya nomor telepon sama sekali."""
    d = {**LAMA, 'phoneNumber': None}
    assert SupplierResponse(**d).phoneNumber is None


def test_surel_tidak_sah_terbaca():
    """
    `EmailStr` menolak alamat yang tidak berbentuk surel — dan menggagalkan
    pembacaan seluruh dokumen karenanya.
    """
    d = {**LAMA, 'email': 'admin@'}
    assert SupplierResponse(**d).email == 'admin@'


def test_aturan_pengisian_tetap_berlaku():
    """
    Melonggarkan pembacaan TIDAK boleh melonggarkan pengisian; yang mengetik
    nomor telepon salah bentuk tetap harus ditolak.
    """
    d = {k: v for k, v in LAMA.items() if k != 'id'}
    with pytest.raises(Exception):
        SupplierCreate(**d)
