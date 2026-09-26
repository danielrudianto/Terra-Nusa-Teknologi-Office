"""
Pengerjaan ujian.

Rute-rute ini TERBUKA — pelamar bukan karyawan dan tidak punya akun. Yang
menandai pesertanya hanya tokennya sendiri, sehingga setiap penjagaan harus
ada di sisi server; tidak ada satu pun yang boleh bergantung pada layar.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(AKAR, 'repository', 'hr_recruitment_repository.py')
RUTE = os.path.join(AKAR, 'routes', 'hr_recruitment_routes.py')


def _fungsi(nama: str) -> str:
    s = open(REPO).read()
    i = s.index(f'async def {nama}(')
    j = s.find('\n    @staticmethod', i)
    return s[i:] if j == -1 else s[i:j]


def test_waktu_mulai_dicatat_server():
    """
    Waktu dari layar dapat diubah siapa pun yang membuka DevTools — dan ujian
    yang timernya dapat diatur peserta tidak mengukur apa pun.
    """
    b = _fungsi('mulai_ujian')
    assert 'dt.now()' in b
    # tidak menerima waktu dari pemanggil
    assert re.search(r'async def mulai_ujian\(token: str\)', b)


def test_mulai_ulang_tidak_menambah_waktu():
    """
    Menutup peramban lalu membukanya kembali adalah celah yang paling mudah
    ditemukan sendiri.
    """
    b = _fungsi('mulai_ujian')
    assert 'if not mulai:' in b


def test_soal_baru_dikirim_setelah_mulai():
    """
    Membaca soal sebelum timer berjalan berarti peserta dapat menyiapkan
    jawaban tanpa waktu berkurang.
    """
    # Yang menentukan bukan apakah tabelnya disentuh — pemeriksaan token
    # memakainya untuk MENGHITUNG jumlah soal, dan itu memang perlu — tetapi
    # apakah ISI soalnya ikut dikembalikan.
    periksa = _fungsi('pelamar_dari_token')
    k = periksa.index('return {')
    assert 'question' not in periksa[k:], 'isi soal bocor saat token diperiksa'

    mulai = _fungsi('mulai_ujian')
    assert 'hr_questions_table.c.question' in mulai


def test_menyimpan_memeriksa_waktu():
    """
    Layar boleh tetap terbuka setelah timernya habis; yang menentukan adalah
    jam server.
    """
    b = _fungsi('simpan_jawaban')
    assert 'sisa_waktu' in b
    assert 'sisa <= 0' in b


def test_jawaban_hanya_untuk_soal_paket_sendiri():
    """
    Muatan dapat disusun sendiri oleh siapa pun. Tanpa penyaringan, jawaban
    dapat ditulis ke soal paket lain.
    """
    b = _fungsi('simpan_jawaban')
    assert 'testID == pelamar["testID"]' in b
    assert 'if qid not in sah:' in b


def test_yang_sudah_dikirim_tidak_dapat_disunting():
    for n in ('mulai_ujian', 'simpan_jawaban', 'kirim_ujian'):
        assert 'submittedAt' in _fungsi(n), n


def test_token_kedaluwarsa_ditolak():
    for n in ('mulai_ujian', 'simpan_jawaban'):
        assert 'expiresAt > dt.now()' in _fungsi(n), n


def test_muatan_dibatasi():
    """
    Rute terbuka tanpa batas muatan hanya ditulis ke basis data sampai penuh.
    """
    s = open(RUTE).read()
    assert '256 * 1024' in s
    for r in ('simpan_jawaban_ujian', 'kirim_ujian'):
        i = s.index(f'async def {r}(')
        j = s.find('\n@router', i)
        assert '_batasi_muatan' in s[i:j if j > 0 else len(s)], r


def test_pembatas_laju_pada_seluruh_rute_ujian():
    s = open(RUTE).read()
    for r in ('mulai_ujian', 'simpan_jawaban_ujian', 'kirim_ujian'):
        i = s.index(f'async def {r}(')
        j = s.find('\n@router', i)
        assert '_jaga_laju' in s[i:j if j > 0 else len(s)], r
