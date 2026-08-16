"""
Penyaring daftar purchase order.

Empat penyaring: status, tipe dokumen, proyek, dan rentang tanggal. Seluruhnya
opsional dan saling melengkapi.

Yang dijaga di sini bukan sekadar bahwa penyaringnya ada, melainkan tiga
keputusan yang mudah terbalik saat kode ini disentuh lagi nanti.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(AKAR, 'repository', 'purchase_order_repository.py')
CTRL = os.path.join(AKAR, 'controllers', 'purchase_order_controller.py')
RUTE = os.path.join(AKAR, 'routes', 'purchase_order_routes.py')


def _blok(berkas: str, nama: str) -> str:
    s = open(berkas).read()
    i = s.index(f'async def {nama}(')
    j = s.find('\n    @staticmethod', i)
    return s[i:] if j == -1 else s[i:j]


def test_penyaring_sampai_ke_repository():
    b = _blok(REPO, 'get_all')
    for p in ('status', 'purchase_type', 'project_name', 'date_from', 'date_to'):
        assert p in b, p


def test_diteruskan_dari_rute_dan_controller():
    """
    Parameter yang berhenti di tengah jalan tidak menimbulkan galat — daftarnya
    sekadar tidak tersaring, dan yang memakainya menyimpulkan penyaringnya
    rusak.
    """
    assert 'purchase_type=purchase_type' in open(RUTE).read()
    assert 'purchase_type=purchase_type' in open(CTRL).read()


def test_rentang_memakai_tanggal_dokumen():
    """
    `date`, bukan `createdAt`.

    Yang dicari saat merekap adalah tanggal dokumennya — yang tercetak dan
    disepakati vendor — bukan kapan barisnya kebetulan dimasukkan ke sistem.
    Keduanya kerap berbeda beberapa hari.
    """
    b = _blok(REPO, 'get_all')
    assert 'purchase_orders_table.c.date >= date_from' in b
    assert 'purchase_orders_table.c.date <= date_to' in b


def test_tipe_menerima_lebih_dari_satu():
    """
    "Semua PO mandor" berarti beberapa kode sekaligus; memilihnya satu per satu
    berarti memuat ulang daftar berkali-kali.
    """
    b = _blok(REPO, 'get_all')
    assert '.in_(tipe)' in b


def test_penghitung_ikut_tersaring():
    """
    Penghitung memakai `conditions` yang sama.

    Bila tidak, jumlah di bawah daftar dan jumlah halamannya menghitung
    seluruh dokumen — dan itu tidak menimbulkan galat, hanya angka yang salah.
    """
    b = _blok(REPO, 'get_all')
    i = b.index('count_query')
    assert '.where(*conditions)' in b[i:i + 500]


def test_penyaring_kosong_tidak_menambah_kondisi():
    """
    Daftar tanpa penyaring harus menghasilkan kueri yang sama seperti sebelum
    penyaring ini ada.
    """
    b = _blok(REPO, 'get_all')
    for p in ('if status ==', 'if purchase_type:', 'if project_name:',
              'if date_from:', 'if date_to:'):
        assert p in b, p
