"""
Sandi selalu di-hash sebelum tersimpan.

Sandi yang tersimpan telanjang terbaca oleh siapa pun yang dapat membuka
tabelnya — termasuk dari cadangan yang bocor. Tidak ada cara memulihkannya
setelah terjadi: yang bocor bukan hash yang perlu dipecahkan, melainkan sandi
itu sendiri, dan orang memakai sandi yang sama di tempat lain.

Dijaga di REPOSITORY, tempat penulisannya benar-benar terjadi. Menjaganya di
controller saja membuat jalur yang melewatinya tidak terlihat — dan itulah
yang terjadi pada `create_user`.
"""

import os
import re

import bcrypt

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(AKAR, 'repository', 'user_repository.py')


def _fungsi_hash():
    s = open(REPO).read()
    i = s.index('def _hash_sandi')
    j = s.index('\ndef _tanpa_sandi')
    ns = {}
    exec('import bcrypt\n' + s[i:j], ns)
    return ns['_hash_sandi']


def _blok(nama: str) -> str:
    s = open(REPO).read()
    i = s.index(f'async def {nama}(')
    j = s.find('async def ', i + 10)
    return s[i:] if j == -1 else s[i:j]


def test_sandi_telanjang_menjadi_hash():
    f = _fungsi_hash()
    h = f('Today@Alpha123')
    assert h.startswith(('$2a$', '$2b$', '$2y$'))
    assert bcrypt.checkpw(b'Today@Alpha123', h.encode())


def test_hash_tidak_di_hash_ulang():
    """
    Pemanggil yang sudah meng-hash sendiri tidak menghasilkan hash berlapis.

    Tanpa penjagaan ini, sandi yang benar pun ditolak saat masuk — dan
    kegagalannya tampak seperti salah ketik, bukan seperti bug.
    """
    f = _fungsi_hash()
    h = f('rahasia')
    assert f(h) == h


def test_pembuatan_pengguna_menghash():
    b = _blok('create_user')
    assert '_hash_sandi' in b, 'create_user menyimpan sandi telanjang'


def test_pembaruan_pengguna_menghash():
    b = _blok('update_user')
    assert '_hash_sandi' in b


def test_tidak_ada_penulis_baru_yang_lolos():
    """Fungsi mana pun yang menulis sandi ke tabel users harus meng-hash."""
    s = open(REPO).read()
    for m in re.finditer(r'async def (\w+)\(', s):
        i = m.start()
        j = s.find('async def ', i + 10)
        b = s[i:] if j == -1 else s[i:j]
        if not re.search(r'insert\(users_table\)|update\(users_table\)', b):
            continue
        if 'password' not in b:
            continue
        assert '_hash_sandi' in b or 'bcrypt' in b, (
            f'{m.group(1)} menulis sandi tanpa meng-hash'
        )
