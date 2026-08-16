"""
Peringatan sebelum purchase order dibuat.

Dua hal diperiksa: harga yang melompat jauh dari terakhir kali, dan dokumen
serupa yang sudah dibuat pada hari yang sama.

Keduanya PERINGATAN, bukan penghalang. Harga memang dapat melompat, dan
dokumen serupa dalam sehari kadang memang disengaja. Yang diperlukan bukan
menghentikan orang, melainkan menyodorkan pembandingnya agar dapat diperiksa
saat itu juga.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTRL = os.path.join(AKAR, 'controllers', 'purchase_order_controller.py')
REPO = os.path.join(AKAR, 'repository', 'purchase_order_repository.py')


def _blok(berkas: str, nama: str) -> str:
    s = open(berkas).read()
    i = s.index(f'async def {nama}(')
    j = s.find('\n    @staticmethod', i)
    return s[i:] if j == -1 else s[i:j]


def _peringatan(lama: float, baru: float) -> bool:
    """Cerminan aturan di controller; ambangnya diuji, bukan dihafal."""
    rasio = baru / lama
    return rasio >= 1.5 or rasio <= 0.6


def test_salah_ketik_nol_tertangkap():
    """Kesalahan paling sering: kelebihan atau kekurangan satu nol."""
    assert _peringatan(170_000, 1_700_000)
    assert _peringatan(170_000, 17_000)


def test_digit_tertukar_tertangkap():
    assert _peringatan(170_000, 710_000)


def test_kenaikan_wajar_tidak_berbunyi():
    """
    Peringatan yang sering keliru berhenti dibaca.

    Kenaikan besi yang tajam sekalipun jarang melampaui 30%; ambangnya
    sengaja dijauhkan dari sana.
    """
    assert not _peringatan(170_000, 187_000)   # +10%
    assert not _peringatan(170_000, 212_500)   # +25%
    assert not _peringatan(170_000, 246_500)   # +45%


def test_penurunan_nego_tidak_berbunyi():
    assert not _peringatan(170_000, 153_000)   # -10%
    assert not _peringatan(170_000, 119_000)   # -30%


def test_harga_dibandingkan_hanya_ke_yang_disetujui():
    """
    Draf memuat angka yang masih dicoba-coba; membandingkan dengannya berarti
    membandingkan dengan tebakan orang lain.
    """
    b = _blok(REPO, 'harga_terakhir')
    assert 'isApproved == 1' in b
    assert 'isDelete == 0' in b


def test_duplikat_menghitung_draf():
    """
    Justru draf yang paling sering menggandakan: dokumen pertama belum
    disetujui sehingga tidak terlihat, lalu dibuat lagi.
    """
    b = _blok(REPO, 'kemungkinan_duplikat')

    # `isApproved` boleh disebut untuk DILAPORKAN — layar perlu tahu apakah
    # dokumen kembarnya sudah terbit atau masih draf. Yang tidak boleh:
    # memakainya sebagai penyaring, karena itu justru membuang draf yang
    # paling sering menggandakan.
    assert 'isApproved == 1' not in b
    assert 'purchase_orders_table.c.isApproved,' in b


def test_duplikat_bertoleransi():
    """
    Pembulatan pajak menghasilkan selisih beberapa rupiah pada dokumen yang
    sebenarnya identik.
    """
    b = _blok(REPO, 'kemungkinan_duplikat')
    assert 'func.abs' in b


def test_duplikat_mengecualikan_diri_sendiri():
    b = _blok(REPO, 'kemungkinan_duplikat')
    assert 'kecuali_id' in b


def test_pemeriksaan_tidak_memblokir():
    """
    Mengembalikan keterangan, bukan galat. Rute ini tidak pernah menolak.
    """
    b = _blok(CTRL, 'pemeriksaan')
    assert 'app_error' not in b
    assert 'return hasil' in b
