"""
Undangan pengisian data hanya untuk karyawan yang masih bekerja.

Karyawan yang keluar TIDAK pernah dihapus — jejaknya diperlukan slip gaji dan
dokumen lama. Tanpa penyaringan, ia tetap muncul sebagai calon penerima
undangan pembaruan data.

Bukan sekadar janggal: tautannya sah tiga hari dan dapat dipakai memperbarui
data orang yang tidak lagi terikat apa pun dengan perusahaan.

Diperiksa di DUA tempat, dan keduanya perlu:

  - saat undangan disusun, supaya tidak dapat diterbitkan sama sekali
  - saat tautannya DIPAKAI, karena orang dapat mengundurkan diri di tengah
    masa berlaku tautan yang sudah terkirim
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERKAS = os.path.join(AKAR, 'repository', 'employee_form_repository.py')


def _blok(nama: str) -> str:
    s = open(BERKAS).read()
    m = re.search(
        rf'\n    async def {nama}\([\s\S]*?'
        r'(?=\n    @staticmethod|\n    async def |\Z)', s)
    assert m, nama
    return m.group(0)


def test_undangan_tidak_dapat_disusun_untuk_yang_keluar():
    assert 'endDate.is_(None)' in _blok('karyawan_ringkas')


def test_tautan_gugur_bila_karyawan_keluar():
    """
    Diperiksa saat DIPAKAI, bukan hanya saat diterbitkan: masa berlaku tiga
    hari cukup panjang untuk seseorang mengundurkan diri di tengahnya.
    """
    assert 'endDate.is_(None)' in _blok('undangan_dari_token')


def test_isDelete_tetap_diperiksa():
    """
    `endDate` menandai berhenti bekerja; `isDelete` menandai baris yang
    dihapus. Keduanya berbeda dan keduanya harus tetap dijaga.
    """
    for nama in ('karyawan_ringkas', 'undangan_dari_token'):
        assert 'isDelete == False' in _blok(nama), nama
