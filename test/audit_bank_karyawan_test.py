"""
Rekening bank dan data karyawan meninggalkan jejak audit.

Keduanya sebelumnya tidak mencatat apa pun. Nomor rekening menentukan ke mana
uang perusahaan berpindah; NIK, jabatan, dan kategori pajak karyawan ikut
menentukan isi slip gaji. Perubahan pada keduanya perlu dapat ditelusuri
sampai ke orangnya.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _blok(berkas: str, nama: str) -> str:
    s = open(os.path.join(AKAR, 'controllers', berkas)).read()
    i = s.index(f'async def {nama}(')
    j = s.find('async def ', i + 10)
    return s[i:] if j == -1 else s[i:j]


def test_rekening_bank_dicatat():
    for fn, aksi in (
        ('create_bank_account', 'create'),
        ('update_bank_account', 'update'),
        ('delete_bank_account', 'delete'),
    ):
        b = _blok('bank_controller.py', fn)
        assert 'AuditLogRepository.record' in b, f'{fn} tidak mencatat'
        assert f'action="{aksi}"' in b, f'{fn} aksinya keliru'


def test_perubahan_rekening_direkam_isinya():
    """
    Keadaan sebelum diubah diambil LEBIH DULU.

    Setelah `execute`, nilai lamanya sudah tertimpa dan tidak dapat direkam
    lagi — jejak yang hanya menyebut "diubah" tanpa menyebut dari apa menjadi
    apa tidak menjawab pertanyaan yang membuatnya diperlukan.
    """
    b = _blok('bank_controller.py', 'update_bank_account')
    assert 'sebelum = await database.fetch_one' in b
    assert b.index('sebelum = await') < b.index('result = await database.execute')
    assert 'AuditLogRepository.diff' in b


def test_karyawan_dicatat():
    for fn, aksi in (('create_employee', 'create'), ('update_employee', 'update')):
        b = _blok('employee_controller.py', fn)
        assert 'AuditLogRepository.record' in b, f'{fn} tidak mencatat'
        assert f'action="{aksi}"' in b


def test_karyawan_hanya_dicatat_bila_berhasil():
    """
    Percobaan yang gagal tidak dicatat.

    Riwayat yang penuh baris tak berdampak memaksa yang menelusuri memilah
    sendiri mana yang benar-benar terjadi.
    """
    b = _blok('employee_controller.py', 'update_employee')
    assert '"error" not in result' in b


def test_pelaku_selalu_disertakan():
    for berkas in ('bank_controller.py', 'employee_controller.py'):
        s = open(os.path.join(AKAR, 'controllers', berkas)).read()
        for m in re.finditer(
            r'AuditLogRepository\.record\(([\s\S]{0,500}?)\n\s*\)\n', s
        ):
            assert 'userID=' in m.group(1), f'{berkas}: pencatatan tanpa pelaku'
