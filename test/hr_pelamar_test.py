"""
Pendaftaran pelamar ujian rekrutmen.

Yang diminta hanya nama dan jenis kelamin; sisanya diisi pelamar sendiri lewat
tautan bertoken. Mengumpulkan alamat dan kontak lebih dulu justru pekerjaan
yang hendak dihilangkan.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(AKAR, 'repository', 'hr_recruitment_repository.py')
RUTE = os.path.join(AKAR, 'routes', 'hr_recruitment_routes.py')
MODEL = os.path.join(AKAR, 'models', 'hr_recruitment_model.py')
SKEMA = os.path.join(AKAR, 'schemas', 'hr_recruitment_schema.py')


def _blok(nama: str) -> str:
    s = open(REPO).read()
    i = s.index(f'async def {nama}(')
    j = s.find('\n    @staticmethod', i)
    return s[i:] if j == -1 else s[i:j]


def test_surel_boleh_kosong():
    """
    Mewajibkannya berarti yang mendaftarkan harus mengumpulkan surel seluruh
    pelamar lebih dulu — dan pada tahap ini sebagian memang belum diketahui.
    """
    s = open(MODEL).read()
    i = s.index('hr_candidates_table')
    j = s.index('\n)', i)
    b = s[i:j]
    k = b.index('"email"')
    assert 'nullable=True' in b[k:k + 120]


def test_gender_ada_di_model():
    s = open(MODEL).read()
    i = s.index('hr_candidates_table')
    j = s.index('\n)', i)
    assert '"gender"' in s[i:j]


def test_token_acak_per_pelamar():
    """
    Nomor berurutan dapat ditebak: satu pelamar tinggal mengubah satu angka
    untuk membuka lembar jawaban pelamar lain.
    """
    b = _blok('daftarkan_pelamar')
    assert 'secrets.token_urlsafe(32)' in b
    # di dalam perulangan, bukan sekali untuk seluruhnya
    assert b.index('for o in orang') < b.index('secrets.token_urlsafe(32)')


def test_baris_kosong_dilewati_bukan_menolak():
    """
    Menempel daftar nama kerap membawa baris kosong di ujungnya, dan menolak
    seluruh permintaan karenanya memaksa yang menempelnya merapikan dulu.
    """
    b = _blok('daftarkan_pelamar')
    assert 'if not nama:' in b
    assert 'continue' in b


def test_jenis_kelamin_hanya_l_atau_p():
    """
    Nilai lain diperlakukan sebagai kosong, bukan disimpan apa adanya —
    kolomnya satu huruf, dan menyimpan "X" membuat penyaringan nanti
    menemukan nilai yang tidak pernah dirancang ada.
    """
    b = _blok('daftarkan_pelamar')
    assert 'in ("L", "P")' in b


def test_jumlah_sekali_kirim_dibatasi():
    """
    Muatan tanpa batas membuat satu permintaan dapat menerbitkan token tanpa
    henti.
    """
    assert 'max_length=200' in open(SKEMA).read()


def test_dijaga_modul_rekrutmen():
    import re

    s = open(RUTE).read()
    i = s.index('/candidates')
    assert 'require("hr_recruitment"' in s[i:i + 600]
