"""
Nilai bertipe `date` harus dapat disandikan JSON.

`datetime` adalah turunan `date`, tetapi TIDAK sebaliknya. Memeriksa
`datetime` saja meloloskan `date` apa adanya, dan penyandiannya gagal dengan
"Object of type date is not JSON serializable".

Kegagalannya ditelan `record()` — operasi utamanya tetap berhasil, hanya
jejaknya yang hilang. Tidak ada yang tampak salah dari layar.

Sudah terjadi pada `endDate` karyawan: lima kali menonaktifkan karyawan, nol
baris di halaman Aktivitas.

Kolom bertipe `Date` juga ada pada purchase order, pinjaman, faktur penjualan,
dan tender — keempatnya kena kelas yang sama.
"""

import json
import os
import re
from datetime import date, datetime
from decimal import Decimal

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERKAS = os.path.join(AKAR, 'repository', 'audit_log_repository.py')


def _sederhanakan():
    src = open(BERKAS).read()
    i = src.index('    def _sederhanakan(nilai):')
    j = src.index('\n    @', i)
    kode = src[i:j].replace('    def', 'def', 1).replace('\n        ', '\n    ')
    ns = {'tanggal': date, 'dt': datetime}
    exec(kode, ns)
    return ns['_sederhanakan']


def test_date_menjadi_teks():
    f = _sederhanakan()
    assert f(date(2025, 12, 9)) == '2025-12-09'


def test_datetime_tetap_ditangani():
    """`datetime` turunan `date`; memeriksa `date` menangkap keduanya."""
    f = _sederhanakan()
    assert f(datetime(2026, 8, 18, 13, 40)).startswith('2026-08-18T13:40')


def test_decimal_menjadi_float():
    f = _sederhanakan()
    assert f(Decimal('1234.56')) == 1234.56


def test_nilai_lain_tidak_diubah():
    f = _sederhanakan()
    assert f('teks') == 'teks'
    assert f(None) is None
    assert f(42) == 42


def test_hasil_dapat_disandikan_json():
    """
    Ujung yang sebenarnya: yang gagal bukan perbandingannya, melainkan
    penyandiannya saat hendak disimpan.
    """
    f = _sederhanakan()
    perubahan = {
        'endDate': {'from': f(None), 'to': f(date(2025, 12, 9))},
        'date': {'from': f(date(2026, 1, 1)), 'to': f(date(2026, 2, 1))},
        'dpp': {'from': f(Decimal('1000')), 'to': f(Decimal('2000.50'))},
    }
    # Tidak boleh melempar.
    json.dumps(perubahan)


def test_memeriksa_date_bukan_hanya_datetime():
    """
    Dijaga pada kodenya, bukan hanya perilakunya: yang kelak menyunting
    fungsi ini perlu tahu bahwa `dt` saja tidak cukup.
    """
    src = open(BERKAS).read()
    i = src.index('def _sederhanakan')
    blok = src[i:i + 900]
    assert 'isinstance(nilai, tanggal)' in blok
    assert 'isinstance(nilai, dt)' not in blok
