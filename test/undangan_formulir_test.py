"""
Pengisian mandiri lewat tautan undangan.

Karyawan mengisi datanya sendiri tanpa akun; tokennya yang menandai siapa dia.
Dua rute karena itu terbuka tanpa penjaga izin — dan justru itu yang menuntut
pemeriksaan paling ketat di berkas ini.

Yang dijaga: siapa yang boleh menerbitkan, dari mana identitas pengisi
diambil, dan berapa lama tautannya hidup.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTE = os.path.join(AKAR, 'routes', 'employee_form_routes.py')
REPO = os.path.join(AKAR, 'repository', 'employee_form_repository.py')
MODEL = os.path.join(AKAR, 'models', 'employee_form_model.py')


def _rute(nama: str) -> str:
    s = open(RUTE).read()
    i = s.index(f'async def {nama}(')
    j = s.find('\n@router.', i)
    return s[i:] if j == -1 else s[i:j]


def test_identitas_diambil_dari_token_bukan_muatan():
    """
    Ini yang paling menentukan.

    Muatan permintaan dapat disusun sendiri oleh siapa pun. Menerima
    `employeeID` dari sana berarti satu orang yang memegang satu tautan dapat
    menimpa data SELURUH karyawan.
    """
    b = _rute('simpan_pengisian_mandiri')
    assert 'undangan["employeeID"]' in b
    assert 'payload.employeeID' not in b
    assert 'employee_id' not in b.split('async def')[0].split(')')[0]


def test_penerbitan_dijaga_izin():
    """
    Menerbitkan tautan berarti memberi seseorang kuasa mengubah datanya
    sendiri — setara dengan mengisi formulir atas namanya.
    """
    b = _rute('terbitkan_undangan')
    assert 'require("employee_form", "update")' in b


def test_token_acak_bukan_urutan():
    """
    Nomor berurutan dapat ditebak: yang menerima tautannya sendiri tinggal
    mengubah satu angka untuk membuka data rekannya.
    """
    b = open(REPO).read()
    assert 'secrets.token_urlsafe' in b


def test_masa_berlaku_tiga_hari():
    b = open(REPO).read()
    assert 'timedelta(days=3)' in b


def test_kedaluwarsa_diperiksa_saat_dibaca():
    """
    Masa berlaku yang hanya disimpan tetapi tidak diperiksa tidak menjaga apa
    pun.
    """
    s = open(REPO).read()
    i = s.index('async def undangan_dari_token')
    j = s.find('\n    @staticmethod', i)
    assert 'expiresAt > dt.now()' in s[i:j]


def test_tiga_kegagalan_dijawab_sama():
    """
    Token tidak dikenal, dicabut, dan kedaluwarsa dijawab identik.

    Membedakannya memberi tahu penebak bahwa tokennya PERNAH ada — dan itu
    keterangan yang tidak perlu diberikan.
    """
    b = _rute('baca_untuk_pengisian')
    assert b.count('Tautan tidak berlaku.') == 1
    assert 'undangan is None' in b


def test_token_tidak_mati_setelah_dipakai():
    """
    Orang kerap menyadari ada yang keliru setelah menekan kirim; token sekali
    pakai memaksanya menghubungi HRD untuk satu huruf.
    """
    s = open(REPO).read()
    i = s.index('async def tandai_terpakai')
    j = s.find('\n    @staticmethod', i)
    b = s[i:j] if j != -1 else s[i:]
    assert 'usedAt' in b
    assert 'isDelete=True' not in b


def test_undangan_lama_dicabut_saat_menerbitkan_baru():
    """
    Dua tautan aktif untuk orang yang sama membuat penerimanya menebak mana
    yang masih hidup.
    """
    s = open(REPO).read()
    i = s.index('async def buat_undangan')
    j = s.find('\n    @staticmethod', i)
    assert 'isDelete=True' in s[i:j]


def test_versi_sama_antara_baca_dan_simpan():
    """
    Menyimpan ke versi yang berbeda dari yang ditampilkan membuat jawabannya
    tercatat pada pertanyaan yang tidak pernah dijawab — tanpa galat apa pun.
    """
    assert 'active_version()' in _rute('baca_untuk_pengisian')
    assert 'active_version()' in _rute('simpan_pengisian_mandiri')


def test_token_unik_di_basis_data():
    s = open(MODEL).read()
    i = s.index('"token"')
    assert 'unique=True' in s[i:i + 120]


def test_undangan_dikirim_lewat_surel():
    """
    Tautan yang hanya diterbitkan tetapi tidak dikirim tidak menolong siapa
    pun: yang menerbitkannya harus menyalinnya sendiri, dan itu persis
    pekerjaan yang hendak dihilangkan.
    """
    b = _rute('terbitkan_undangan')
    assert 'MailService.send_email(' in b


def test_gagal_kirim_tidak_menggagalkan_penerbitan():
    """
    Tokennya sudah dibuat dan sah.

    Menggagalkan seluruh permintaan karena surelnya tidak terkirim berarti
    menerbitkan token kedua untuk orang yang sama — dan yang menerima dua
    tautan harus menebak mana yang hidup.
    """
    b = _rute('terbitkan_undangan')
    i = b.index('MailService.send_email(')
    assert 'except Exception' in b[i:]
    assert 'emailTerkirim' in b


def test_alamat_frontend_dari_lingkungan():
    """
    Server klien lain memakai domain berbeda; tautan yang menunjuk ke domain
    AKN tidak akan pernah terbuka bagi mereka.
    """
    s = open(RUTE).read()
    assert 'os.getenv("FRONTEND_URL"' in s


def test_nama_pengundang_tidak_menjatuhkan_rute():
    """
    Objek dari `require()` adalah Record, bukan dict — kolom yang tidak ada
    melempar galat dengan jejak tumpukan yang tidak menyebut sebabnya.
    """
    b = _rute('terbitkan_undangan')
    i = b.index('user["name"]')
    assert 'except (KeyError, TypeError)' in b[i:i + 200]
