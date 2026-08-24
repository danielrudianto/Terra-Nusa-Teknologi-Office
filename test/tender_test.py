"""
Tender pengadaan.

Yang dijaga di sini bukan alur bahagianya, melainkan keadaan-keadaan yang
membuat keputusan pengadaan tidak dapat ditinjau kemudian.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTRL = os.path.join(AKAR, 'controllers', 'tender_controller.py')
REPO = os.path.join(AKAR, 'repository', 'tender_repository.py')
SKEMA = os.path.join(AKAR, 'schemas', 'tender_schema.py')


def _blok(berkas: str, nama: str) -> str:
    s = open(berkas).read()
    m = re.search(
        rf'\n    async def {nama}\([\s\S]*?'
        r'(?=\n    @staticmethod|\n    async def |\Z)', s)
    assert m, nama
    return m.group(0)


def test_pemenang_menuntut_tiga_penawaran():
    """
    Keputusan yang hanya membandingkan dua penawaran mudah tampak wajar
    padahal tidak pernah diuji pasar — dan yang meninjaunya kelak tidak punya
    cara mengetahui bahwa pembandingnya memang tidak ada.
    """
    from repository.tender_repository import MINIMAL_PENAWARAN
    assert MINIMAL_PENAWARAN >= 3
    assert 'MINIMAL_PENAWARAN' in _blok(CTRL, 'tetapkan_pemenang')


def test_alasan_pemenang_wajib():
    """
    Pemenang tidak selalu yang termurah. Tanpa alasan tertulis, keputusannya
    tidak dapat ditinjau siapa pun setelah orangnya berganti.
    """
    s = open(SKEMA).read()
    m = re.search(r'class TenderPemenang[\s\S]*?(?=\nclass |\Z)', s)
    assert 'winnerReason: str = Field(min_length=' in m.group(0)


def test_satu_pemasok_satu_penawaran():
    """
    Dua penawaran dari pemasok yang sama membuat perbandingan menampilkan satu
    nama dua kali dengan angka berbeda.
    """
    assert 'pemasok_sudah_menawar' in _blok(CTRL, 'tambah_penawaran')


def test_baris_penawaran_disaring_ke_tendernya():
    """
    `tenderItemID` datang dari layar dan dapat menunjuk ke mana saja. Tanpa
    penyaringan, satu penawaran dapat menuliskan harga pada baris tender LAIN.
    """
    for fn in ('tambah_penawaran', 'ubah_penawaran'):
        b = _blok(CTRL, fn)
        assert 'sah' in b and 'tenderItemID' in b, fn


def test_tender_selesai_tidak_dapat_diubah():
    b = _blok(CTRL, 'ubah')
    assert 'STATUS_DAPAT_DISUNTING' in b


def test_tender_selesai_tidak_dapat_dihapus():
    """Riwayat pengadaan harus tetap dapat ditinjau."""
    assert 'selesai' in _blok(CTRL, 'hapus')


def test_penawaran_pemenang_tidak_dapat_dihapus():
    assert 'winnerQuoteID' in _blok(CTRL, 'hapus_penawaran')


def test_baris_tanpa_harga_tidak_disimpan():
    """
    Kosong berbeda dari nol: nol berarti digratiskan, kosong berarti tidak
    ditawar — dan yang tidak menawar tidak boleh terhitung sebagai termurah.
    """
    s = open(REPO).read()
    m = re.search(
        r'\n    async def _tulis_baris_penawaran\([\s\S]*?'
        r'(?=\n    @staticmethod|\n    async def |\Z)', s)
    assert 'is None:' in m.group(0) and 'continue' in m.group(0)


def test_nomor_dari_max_bukan_count():
    """
    `COUNT` membuat nomor terpakai ulang setelah ada tender dihapus — dan dua
    tender bernomor sama membuat rujukan pada percakapan WhatsApp menjadi taksa.
    """
    b = _blok(REPO, 'nomor_berikutnya')
    assert 'func.max' in b and 'func.count' not in b


def test_izin_approve_terpisah_dari_update():
    """
    Yang mencatat penawaran belum tentu yang berhak memutuskan pemenangnya.
    """
    s = open(os.path.join(AKAR, 'routes', 'tender_routes.py')).read()
    m = re.search(r'@router\.post\("/\{tender_id\}/pemenang"\)[\s\S]{0,400}', s)
    assert '"tender", "approve"' in m.group(0)


def test_tender_terdaftar_di_matriks_izin():
    s = open(os.path.join(AKAR, 'constants', 'permission_matrix.py')).read()
    assert '"tender":' in s


def test_tender_masuk_wilayah_procurement():
    s = open(os.path.join(AKAR, 'constants', 'department_modules.py')).read()
    m = re.search(r'"procurement": UMUM[\s\S]*?\n    \}', s)
    assert '"tender"' in m.group(0)
