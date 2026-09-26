"""
Persetujuan purchase order.

Menyetujui harus menulis EMPAT hal: status, penandanya, siapa yang
menyetujui, dan kapan. Menulis salah satunya saja menghasilkan dokumen yang
tampak sah di layar tetapi tercetak tanpa nama penyetuju — dan itu tidak
menimbulkan galat apa pun.

Sudah terjadi: seluruh purchase order tercatat `isApproved = 0` walau
statusnya sudah "approved", dan blok tanda tangannya kosong pada setiap
lembar yang dicetak.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(AKAR, 'repository', 'purchase_order_repository.py')


def _blok(nama: str) -> str:
    s = open(REPO).read()
    i = s.index(f'async def {nama}(')
    j = s.find('\n    @staticmethod', i)
    return s[i:] if j == -1 else s[i:j]


def test_menyetujui_menulis_empat_kolom():
    b = _blok('update_status')
    assert 'isApproved=True' in b
    assert 'approvedBy=user_id' in b
    assert 'approvedAt=dt.now()' in b
    assert '"status": status' in b


def test_membatalkan_mencabut_jejak_persetujuan():
    """
    Menyisakan `approvedBy` pada dokumen yang tidak lagi sah membuat orang
    yang namanya tercantum tampak menyetujui sesuatu yang sudah ditarik.
    """
    b = _blok('update_status')
    assert 'isApproved=False' in b
    assert 'approvedBy=None' in b
    assert 'approvedAt=None' in b


def test_pembuat_tidak_menyetujui_sendiri():
    """
    Penjagaan ini harus ada di `update_status`, bukan hanya di `approve()` —
    yang terakhir tidak pernah dipanggil dari rute mana pun.
    """
    b = _blok('update_status')
    assert 'boleh_menyetujui_sendiri' in b


def test_nama_penyetuju_ikut_dibaca():
    """
    Yang tersimpan hanya `approvedBy` berupa ID; tanpa join, dokumen hanya
    tahu ADA yang menyetujui tetapi tidak tahu siapa.
    """
    b = _blok('get_by_id')
    assert 'approvedByName' in b
    assert 'approvedByPosition' in b
