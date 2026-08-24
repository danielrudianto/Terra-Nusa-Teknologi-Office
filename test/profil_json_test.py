"""
Kolom JSON pada profil karyawan harus sampai sebagai daftar, bukan teks.

`databases` mengembalikan kolom JSON MySQL apa adanya — sebagai string.
Layar memeriksanya dengan `Array.isArray()`, yang menolak string, sehingga
seluruh bagian itu tidak pernah ditampilkan.

Tidak ada galat di mana pun: datanya tersimpan benar, jawabannya berisi, dan
layarnya menyimpulkan bagian itu memang kosong. Yang membukanya menanyakan
ulang pendidikan dan susunan keluarga kepada orangnya.
"""

import json
import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERKAS = os.path.join(AKAR, 'repository', 'employee_profile_repository.py')


def _rapikan():
    src = open(BERKAS).read()
    i = src.index('_KOLOM_JSON = (')
    j = src.index('\nclass ')
    ns = {'json': json}
    exec('import json\n' + src[i:j], ns)
    return ns['_rapikan']


def test_teks_json_menjadi_daftar():
    r = _rapikan()
    h = r({'formalEducation': '[{"level":"S1","school":"ITB"}]'})
    assert isinstance(h['formalEducation'], list)
    assert h['formalEducation'][0]['level'] == 'S1'


def test_seluruh_kolom_daftar_ikut_diurai():
    """
    Kolom baru yang lupa didaftarkan akan sampai sebagai teks dan bagiannya
    hilang dari layar — tanpa satu pun tanda.
    """
    src = open(BERKAS).read()
    i = src.index('_KOLOM_JSON = (')
    daftar = src[i:src.index(')', i)]
    for kolom in ('drivingLicenses', 'formalEducation', 'workExperience',
                  'languages', 'familyMembers'):
        assert kolom in daftar, kolom


def test_isi_rusak_dibiarkan():
    """
    Mengosongkannya menghapus data yang mungkin masih dapat diselamatkan
    tangan; membiarkannya membuat masalahnya terlihat.
    """
    r = _rapikan()
    h = r({'formalEducation': '{bukan json'})
    assert h['formalEducation'] == '{bukan json'


def test_none_tidak_diubah():
    r = _rapikan()
    assert r({'formalEducation': None})['formalEducation'] is None
    assert r(None) is None


def test_setiap_pembaca_memakai_rapikan():
    """
    `dict(row)` langsung melewatkan kolom JSON sebagai teks.
    """
    s = open(BERKAS).read()
    assert 'return dict(row)' not in s
    assert 'return [dict(r) for r in rows]' not in s


# ---------------------------------------------------------------------------
# Formulir isi sendiri
# ---------------------------------------------------------------------------

BERKAS_FORM = os.path.join(AKAR, 'repository', 'employee_form_repository.py')


def test_setiap_pembaca_versi_mengurai_fields():
    """
    `fields` berkolom JSON dan driver mengembalikannya sebagai TEKS.

    Yang tidak menguraikannya membuat daftar versi menghitung PANJANG STRING
    alih-alih banyaknya isian — dan layar pengisian yang menerimanya lewat
    `Array.isArray()` menampilkan formulir kosong tanpa satu pun galat.
    """
    s = open(BERKAS_FORM).read()

    # Setiap fungsi yang mengembalikan baris versi harus menguraikannya.
    import re
    for nama in ('active_version', 'list_versions'):
        m = re.search(
            rf'\n    async def {nama}\([\s\S]*?'
            r'(?=\n    @staticmethod|\n    async def |\Z)', s)
        assert m, nama
        assert '_baca_jawaban' in m.group(0), f'{nama} tidak mengurai fields'


def test_baris_versi_tidak_dikembalikan_apa_adanya():
    s = open(BERKAS_FORM).read()
    import re
    m = re.search(
        r'\n    async def list_versions\([\s\S]*?'
        r'(?=\n    @staticmethod|\n    async def |\Z)', s)
    assert 'return [dict(r) for r in await database.fetch_all(query)]' \
        not in m.group(0)
