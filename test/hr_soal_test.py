"""
Bank soal ujian rekrutmen.

Soalnya esai dan dinilai orang; tidak ada kunci jawaban yang disimpan. Yang
dijaga di sini adalah keputusan yang mudah terbalik saat kode ini disentuh
lagi — masing-masing menghasilkan perilaku yang tampak wajar tetapi salah.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(AKAR, 'repository', 'hr_recruitment_repository.py')
RUTE = os.path.join(AKAR, 'routes', 'hr_recruitment_routes.py')
SKEMA = os.path.join(AKAR, 'schemas', 'hr_recruitment_schema.py')


def _blok(berkas: str, nama: str) -> str:
    s = open(berkas).read()
    i = s.index(f'async def {nama}(')
    j = s.find('\n    @staticmethod', i)
    return s[i:] if j == -1 else s[i:j]


def test_seluruh_rute_dijaga_modul_rekrutmen():
    """
    Satu rute yang lolos penjagaan membuka seluruh bank soal kepada siapa pun
    yang punya akun.
    """
    import re

    s = open(RUTE).read()
    rute = re.findall(r'@router\.\w+\("([^"]*)"\)', s)
    penjaga = re.findall(r'require\("(\w+)", "(\w+)"\)', s)

    # Rute `/exam/...` SENGAJA terbuka.
    #
    # Yang menandai pesertanya adalah tokennya sendiri; pelamar bukan karyawan
    # dan tidak punya akun. Daftarnya disebut SATU PER SATU di sini supaya
    # rute terbuka BERIKUTNYA tidak lolos diam-diam — yang lupa dijaga tidak
    # akan ada di daftar ini dan menggagalkan uji.
    TERBUKA = {
        '/exam/{token}',           # periksa token, tanpa soal
        '/exam/{token}/mulai',     # mulai mengerjakan, kirim soal
        '/exam/{token}/jawaban',   # simpan jawaban berkala
        '/exam/{token}/kirim',     # kirim jawaban akhir
    }
    terbuka = [r for r in rute if r.startswith('/exam/')]
    assert set(terbuka) == TERBUKA, sorted(set(terbuka) ^ TERBUKA)
    assert len(rute) - len(terbuka) == len(penjaga), (rute, penjaga)
    assert all(m == 'hr_recruitment' for m, _ in penjaga), penjaga


def test_menghapus_menandai_bukan_membuang():
    """
    Jawaban lama menunjuk ke soal ini. Menghapus barisnya membuat lembar
    jawaban yang sudah dinilai kehilangan pertanyaannya — dan nilai tanpa
    pertanyaan tidak dapat ditinjau ulang oleh siapa pun.
    """
    b = _blok(REPO, 'hapus_soal')
    assert 'isDelete=True' in b
    assert 'delete(' not in b


def test_createdAt_diisi_manual():
    """
    Default kolom sisi-Python tidak pernah berlaku pada pustaka `databases`:
    kueri yang dieksekusi sudah terkompilasi, sehingga langkah itu dilewati
    dan nilainya sampai ke MySQL sebagai NULL.
    """
    b = _blok(REPO, 'buat_soal')
    assert 'createdAt=dt.now()' in b


def test_urutan_diisi_otomatis():
    """
    Yang membuat soal memikirkan isinya, bukan nomor ke berapa ia muncul.
    """
    b = _blok(REPO, 'buat_soal')
    assert 'func.max(hr_questions_table.c.sortOrder)' in b


def test_pencarian_menyentuh_catatan():
    """
    Sebagian soal hanya dapat ditemukan lewat standar yang disebut di
    catatannya — "SNI-03" tidak muncul di pertanyaannya sama sekali.
    """
    b = _blok(REPO, 'daftar_soal')
    assert 'notes.ilike' in b


def test_ubah_hanya_menyentuh_yang_dikirim():
    """
    Tanpa `exclude_unset`, seluruh kolom tertimpa `None` pada setiap
    penyuntingan kecil — dan itu tidak menimbulkan galat, hanya soal yang
    kehilangan catatan dan lampirannya.
    """
    assert 'exclude_unset=True' in open(RUTE).read()


def test_soal_dihapus_tidak_ikut_daftar():
    b = _blok(REPO, 'daftar_soal')
    assert 'isDelete == False' in b


def test_panjang_isian_dibatasi():
    """
    Kolomnya `TEXT`, tetapi isian tanpa batas membuat satu orang dapat
    menyimpan berkilo-kilo teks tanpa disengaja.
    """
    s = open(SKEMA).read()
    assert 'max_length=2000' in s
    assert 'max_length=500' in s
