"""
Draf pembelian meninggalkan jejak audit.

Sebelumnya draf dibuat, dikonversi, dan dihapus tanpa satu baris pun di
Aktivitas. Tidak ada galat: dokumennya tersimpan, layarnya bekerja, dan
ketiadaannya baru terlihat ketika ada yang mencari.

Draf memuat nilai dokumen dan pemasoknya, dan konversinya melahirkan
pembelian yang benar-benar ditagihkan — dua alasan yang membuat jejaknya
diperlukan.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERKAS = os.path.join(AKAR, 'controllers', 'purchase_draft_controller.py')


def _blok(nama: str) -> str:
    s = open(BERKAS).read()
    i = s.index(f'async def {nama}(')
    j = s.find('async def ', i + 10)
    return s[i:] if j == -1 else s[i:j]


def test_pembuatan_dicatat():
    b = _blok('create_purchase_draft')
    assert 'AuditLogRepository.record' in b
    assert 'entity="purchase_draft"' in b
    assert 'action="create"' in b


def test_penghapusan_dicatat():
    b = _blok('delete_purchase_draft')
    assert 'AuditLogRepository.record' in b
    assert 'action="delete"' in b


def test_konversi_dicatat_dua_arah():
    """
    Penelusurannya dua arah.

    Yang melihat sebuah pembelian ingin tahu ia berasal dari draf mana; yang
    melihat draf ingin tahu ia menjadi pembelian mana. Satu catatan saja
    membuat salah satu arah itu buntu.
    """
    b = _blok('convert_purchase_draft')
    assert b.count('AuditLogRepository.record') >= 2
    assert 'entity="purchase_draft"' in b
    assert 'entity="purchases"' in b
    assert '"purchaseID"' in b
    assert '"purchaseDraftID"' in b


def test_pelaku_selalu_disertakan():
    """
    Jejak tanpa pelaku tidak menjawab pertanyaan yang membuatnya diperlukan.
    """
    s = open(BERKAS).read()
    for m in re.finditer(r'AuditLogRepository\.record\(([\s\S]{0,400}?)\n\s*\)', s):
        assert 'userID=' in m.group(1), 'ada pencatatan tanpa pelaku'
