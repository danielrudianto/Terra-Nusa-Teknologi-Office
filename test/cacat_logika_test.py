"""
Tindakan yang tidak boleh dilakukan pada keadaan tertentu.

Kelas kesalahan yang sama berulang: sebuah tindakan diizinkan tanpa memeriksa
apakah sasarannya masih dalam keadaan yang membolehkannya. Tidak ada galat —
tindakannya berhasil, dan akibatnya baru terlihat jauh kemudian.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _blok(berkas: str, nama: str) -> str:
    s = open(os.path.join(AKAR, berkas)).read()
    m = re.search(
        rf'\n    async def {nama}\([\s\S]*?'
        r'(?=\n    @staticmethod|\n    async def |\Z)', s)
    assert m, f'{berkas}::{nama}'
    return m.group(0)


def test_pembayaran_disetujui_tidak_dapat_dihapus():
    """
    Persetujuan adalah titik ketika uangnya dinyatakan boleh keluar;
    menghapusnya sesudah itu menghilangkan jejak keputusan yang sudah diambil,
    dan saldo bank tidak ikut kembali.
    """
    b = _blok('controllers/payment_outgoing_controller.py',
              'delete_payment_by_id')
    assert 'isApprove' in b


def test_draf_terkonversi_tidak_dapat_dihapus():
    """
    Pembeliannya menunjuk balik ke draf lewat `purchaseID`; menghapus drafnya
    membuat pembelian yang sudah berjalan kehilangan asal-usulnya.
    """
    b = _blok('controllers/purchase_draft_controller.py',
              'delete_purchase_draft')
    assert 'convertedAt' in b


def test_pesan_hapus_draf_tidak_menyebut_konversi():
    """
    Pesan sebelumnya menyebut "converted" pada fungsi yang MENGHAPUS — dua
    peristiwa yang berlawanan artinya.
    """
    b = _blok('controllers/purchase_draft_controller.py',
              'delete_purchase_draft')
    assert 'Purchase draft converted successfully' not in b
