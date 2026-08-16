"""
Nama reimbursement unik.

Nama dipakai sebagai penyebut pada dokumen pembayaran dan rekap; dua
reimbursement bernama sama membuat yang menyetujui tidak dapat memastikan
mana yang sedang dibayarnya.

Basis data sudah membatasinya sejak awal, tetapi kode tidak mengetahuinya —
sehingga nama yang sudah terpakai ditolak dengan galat 500 tanpa keterangan,
dan yang mengisinya menyimpulkan sistemnya rusak lalu mencoba lagi dengan
nama yang sama.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(AKAR, 'models', 'reimbursement_model.py')
REPO = os.path.join(AKAR, 'repository', 'reimbursement_repository.py')


def test_dinyatakan_unik_di_model():
    """
    Dinyatakan di model, bukan hanya di basis data.

    `cek_skema` membandingkan keduanya; batasan yang hanya ada di satu sisi
    muncul sebagai peringatan pada setiap deploy, dan peringatan yang selalu
    ada berhenti dibaca.
    """
    s = open(MODEL).read()
    i = s.index('"name"')
    assert 'unique=True' in s[i:i + 120]


def test_nama_ganda_ditolak_dengan_pesan():
    """
    Bukan galat 500. Yang mengisinya harus tahu bahwa namanya sudah terpakai.
    """
    s = open(REPO).read()
    i = s.index('async def create_reimbursement(')
    j = s.find('async def ', i + 10)
    b = s[i:j]
    assert 'IntegrityError' in b
    assert 'Duplicate entry' in b
    assert 'ErrorCode.VALIDATION' in b


def test_galat_lain_tetap_internal():
    """
    Hanya nama ganda yang dijelaskan.

    Galat basis data lain kerap memuat nama tabel, nama kolom, dan potongan
    SQL — menyampaikannya apa adanya membocorkan bentuk basis data kepada
    siapa pun yang menekan simpan.
    """
    s = open(REPO).read()
    i = s.index('async def create_reimbursement(')
    j = s.find('async def ', i + 10)
    b = s[i:j]
    assert b.count('internal_error()') >= 2
