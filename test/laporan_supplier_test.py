"""
Laporan satu pemasok.

Dibuka dari data master, menampilkan ringkasan nilai, sebaran proyek, dan
dokumen terakhir pemasok tersebut.

Yang dijaga di sini adalah keputusan-keputusan yang mudah terbalik saat kode
ini disentuh lagi — masing-masing menghasilkan angka yang tampak wajar tetapi
salah, dan angka yang salah pada laporan keuangan tidak menimbulkan galat apa
pun.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(AKAR, 'repository', 'supplier_repository.py')
RUTE = os.path.join(AKAR, 'routes', 'supplier_routes.py')


def _blok(nama: str) -> str:
    s = open(REPO).read()
    i = s.index(f'async def {nama}(')
    j = s.find('\n    @staticmethod', i)
    return s[i:] if j == -1 else s[i:j]


def test_dihitung_dari_pembelian_bukan_purchase_order():
    """
    Purchase order adalah pesanan; sebagian tidak pernah ditagih, sebagian
    ditagih dengan nilai berbeda karena volume terpasang tidak sama dengan
    yang dipesan.
    """
    b = _blok('laporan')
    assert 'purchases_table' in b
    assert 'purchase_orders_table' not in b


def test_ppn_diperlakukan_sebagai_persen():
    """
    Disimpan sebagai persen, bukan rupiah. Mengalikannya langsung
    menghasilkan angka yang terlalu kecil sepersekian ribu kali.
    """
    b = _blok('laporan')
    assert 'ppn * purchases_table.c.dpp / 100' in b


def test_lewat_tempo_menuntut_dua_syarat():
    """
    Belum lunas DAN tanggal jatuh temponya sudah lewat.

    Yang belum lunas tetapi belum jatuh tempo bukan tunggakan — menghitungnya
    sebagai tunggakan membuat setiap pemasok tampak menunggak.
    """
    b = _blok('laporan')
    assert 'isPaid == False' in b
    assert 'dueDate < func.curdate()' in b
    assert 'dueDate.isnot(None)' in b


def test_dokumen_dihapus_tidak_dihitung():
    b = _blok('laporan')
    assert 'isDelete == False' in b


def test_penyaring_opsional():
    """
    Tanpa penyaring, laporannya mencakup seluruh riwayat pemasok tersebut.
    """
    b = _blok('laporan')
    for p in ('if date_from:', 'if date_to:', 'if project_name:'):
        assert p in b, p


def test_dijaga_izin_baca_supplier():
    """
    Isinya rekapan dari data yang sudah boleh dilihat orang tersebut, bukan
    keterangan baru — sehingga izinnya sama dengan melihat pemasoknya.
    """
    s = open(RUTE).read()
    i = s.index('/{supplier_id}/laporan')
    assert 'require("supplier", "read")' in s[i:i + 400]
