"""
Pemilih penanggung jawab pada purchase order.

Rute ini mengembalikan nama dan telepon karyawan aktif saja. Ia SENGAJA
terpisah dari `GET /employees`: modul `employees` termasuk
`MODUL_WILAYAH_MUTLAK` — isinya susunan keluarga, riwayat kesehatan, dan gaji,
yang hanya terbuka bagi HRD.

Yang membuat purchase order tidak perlu melihat semua itu. Membuka rute
`employees` untuk keperluan ini berarti membuka seluruh isinya kepada
procurement.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTE = os.path.join(AKAR, 'routes', 'employees_routes.py')
MODEL = os.path.join(AKAR, 'models', 'employee_model.py')


def _blok(nama: str) -> str:
    s = open(MODEL).read()
    i = s.index(f'async def {nama}(')
    j = s.find('\n    @staticmethod', i)
    return s[i:] if j == -1 else s[i:j]


def test_dijaga_izin_membuat_po_bukan_baca_karyawan():
    """
    `employees:read` hanya dimiliki HRD; memakainya di sini membuat
    autocomplete selalu kosong bagi procurement yang justru memerlukannya.
    """
    s = open(RUTE).read()
    i = s.index('/pilihan-pic')
    blok = s[i:i + 900]
    assert 'require("purchase_order", "create")' in blok
    assert 'require("employees"' not in blok


def test_hanya_mengembalikan_nama_dan_kontak():
    """
    Tabel karyawan memuat gaji, riwayat kesehatan, dan susunan keluarga.
    Mengembalikan barisnya apa adanya membocorkan seluruhnya.
    """
    b = _blok('pilihan_pic')
    k = b.index('return [')
    dikembalikan = b[k:]
    for terlarang in ('nik', 'birthday', 'address', 'taxCategory', 'email'):
        assert f'"{terlarang}"' not in dikembalikan, terlarang


def test_hanya_karyawan_aktif():
    """
    Mencantumkan yang sudah berhenti pada dokumen baru berarti vendor
    menghubungi orang yang tidak lagi bekerja di sini.
    """
    b = _blok('pilihan_pic')
    assert 'isDelete == False' in b
    assert 'endDate' in b


def test_jumlah_dibatasi():
    """
    Daftar tanpa batas membuat setiap ketukan huruf menarik seluruh karyawan.
    """
    b = _blok('pilihan_pic')
    assert '.limit(' in b


def test_rute_didaftarkan_sebelum_id():
    """
    FastAPI mencocokkan rute berurutan dan menjalankan dependensinya sebelum
    memeriksa tipe jalurnya; "pilihan-pic" akan tertangkap sebagai id.
    """
    import re

    s = open(RUTE).read()
    urut = [m.group(1) for m in re.finditer(r'@router\.\w+\("([^"]*)"', s)]
    assert urut.index('/pilihan-pic') < urut.index('/{employee_id}')
