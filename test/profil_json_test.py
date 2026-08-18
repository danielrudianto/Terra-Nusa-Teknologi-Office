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
