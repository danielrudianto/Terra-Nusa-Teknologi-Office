"""
Kolom sandi tidak pernah meninggalkan server.

Yang tersimpan memang hash bcrypt, bukan sandi terbaca. Tetapi hash itu tetap
tidak boleh keluar: ia dapat diserang secara luring tanpa batas percobaan, dan
sekali bocor tidak ada cara menariknya kembali.

Kebocorannya tidak menimbulkan galat — datanya sekadar ikut terbawa pada
jawaban, dan baru terlihat oleh yang membuka Network tab.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(AKAR, 'repository', 'user_repository.py')

#: Fungsi yang memang memerlukan kolom sandi.
DIKECUALIKAN = {'get_user_by_email'}


def _blok(nama: str) -> str:
    s = open(REPO).read()
    i = s.index(f'async def {nama}(')
    j = s.find('async def ', i + 10)
    return s[i:] if j == -1 else s[i:j]


def test_helper_ada():
    s = open(REPO).read()
    assert 'def _tanpa_sandi' in s
    assert 'pop("password", None)' in s


def test_pembaca_membuang_sandi():
    for fn in ('get_user_by_id', 'get_users', 'create_user'):
        b = _blok(fn)
        assert '_tanpa_sandi' in b, f'{fn} tidak membuang sandi'


def test_login_tetap_menerima_sandi():
    """
    Login membandingkan sandi yang dikirim dengan hash tersimpan.

    Membuang kolomnya di sini akan membuat setiap upaya masuk gagal — dan
    kegagalannya tampak seperti sandi yang salah, bukan seperti bug.
    """
    b = _blok('get_user_by_email')
    assert '_tanpa_sandi' not in b


def test_tidak_ada_pembaca_baru_yang_lolos():
    """
    Fungsi mana pun yang MENGEMBALIKAN baris users harus membuang sandinya.

    Yang hanya mengembalikan pesan tidak membocorkan apa pun, sehingga
    dikecualikan.
    """
    s = open(REPO).read()
    for m in re.finditer(r'async def (\w+)\(', s):
        nama = m.group(1)
        if nama in DIKECUALIKAN:
            continue
        i = m.start()
        j = s.find('async def ', i + 10)
        b = s[i:] if j == -1 else s[i:j]

        if not re.search(
            r'select\(\s*users_table\s*[,)]|users_table\.select\(\)', b
        ):
            continue
        balikan = re.findall(r'return ([^\n]+)', b)
        if not any(
            k in r for r in balikan for k in ('dict(', 'result', 'rows', '_tanpa_sandi')
        ):
            continue
        assert '_tanpa_sandi' in b, f'{nama} mengembalikan baris tanpa membuang sandi'
