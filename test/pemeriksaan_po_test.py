"""
Tahap pemeriksaan purchase order.

Dokumen melewati dua tangan: diperiksa dulu, baru disetujui. Pemeriksa
membaca isinya — harga, volume, spesifikasi; penyetuju memutuskan dokumen itu
boleh terbit.

Dipisah karena keduanya menjawab pertanyaan yang berbeda, dan yang
menggabungkannya berarti satu orang menjawab keduanya sendirian.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(AKAR, 'repository', 'purchase_order_repository.py')
RUTE = os.path.join(AKAR, 'routes', 'purchase_order_routes.py')


def _blok(nama: str) -> str:
    s = open(REPO).read()
    i = s.index(f'async def {nama}(')
    j = s.find('\n    @staticmethod', i)
    return s[i:] if j == -1 else s[i:j]


def test_pemeriksa_level_3_harus_procurement():
    from utils.permission import boleh_memeriksa

    assert boleh_memeriksa(3, {'procurement'})
    assert not boleh_memeriksa(3, {'fat'})
    assert not boleh_memeriksa(3, set())


def test_level_4_dan_5_memeriksa_tanpa_divisi():
    """
    Keduanya berwenang atas seluruh dokumen, dan kerap merekalah satu-satunya
    yang hadir — memaksa mereka lewat divisi hanya menghentikan pekerjaan.
    """
    from utils.permission import boleh_memeriksa

    assert boleh_memeriksa(4, set())
    assert boleh_memeriksa(5, set())


def test_di_bawah_level_3_tidak_memeriksa():
    from utils.permission import boleh_memeriksa

    assert not boleh_memeriksa(2, {'procurement'})
    assert not boleh_memeriksa(1, {'procurement'})


def test_pembuat_tidak_memeriksa_sendiri_termasuk_pemilik():
    """
    Pemeriksaan justru ADA untuk menghadirkan mata kedua; membiarkan
    pembuatnya memeriksa sendiri membuat tahap ini hanya menambah satu klik
    tanpa menambah apa pun.
    """
    from utils.permission import boleh_memeriksa_sendiri

    for lv in (3, 4, 5):
        assert not boleh_memeriksa_sendiri(lv), lv


def test_level_4_tidak_menyetujui_dokumen_sendiri():
    """
    Dinaikkan dari 4 ke 5 atas keputusan pemilik: menyetujui dokumen sendiri
    menghapus satu-satunya pemeriksaan yang tersisa.
    """
    from utils.permission import boleh_menyetujui_sendiri

    assert not boleh_menyetujui_sendiri(4)
    assert boleh_menyetujui_sendiri(5)


def test_belum_diperiksa_tidak_dapat_disetujui():
    """
    Menyetujui yang belum diperiksa berarti memutuskan tanpa seorang pun
    membaca isinya lebih dulu.
    """
    b = _blok('update_status')
    assert 'isChecked' in b
    assert 'belum diperiksa' in b.lower()


def test_mencabut_pemeriksaan_menggugurkan_persetujuan():
    """
    Dokumen yang sudah disetujui lalu pemeriksaannya dibatalkan tidak boleh
    tetap tercetak sah — yang menandatanganinya bertumpu pada pemeriksaan
    yang ternyata ditarik.
    """
    b = _blok('set_checked')
    assert '"isApproved": False' in b
    assert '"status": "draft"' in b


def test_divisi_dibaca_dari_basis_data():
    """
    Objek yang dikembalikan `require()` tidak memuat divisi sama sekali —
    membacanya dari sana selalu menghasilkan kosong, dan setiap procurement
    level 3 ditolak tanpa sebab yang terlihat.
    """
    b = _blok('set_checked')
    assert '_departments(user_id)' in b


def test_memeriksa_dijaga_izin_update_bukan_approve():
    """
    Memeriksa bukan menyetujui; menyamakan izinnya berarti setiap pemeriksa
    otomatis dapat menerbitkan dokumen tanpa seorang pun memutuskannya.
    """
    s = open(RUTE).read()
    i = s.index('/{purchase_order_id}/checked')
    assert 'require("purchase_order", "update")' in s[i:i + 400]
