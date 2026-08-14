"""
Purchase order yang sudah selesai tidak boleh disetujui atau dihapus lagi.

Menyembunyikan tombolnya saja tidak cukup: layar dapat dilewati, dan yang
menjaga keutuhan dokumen harus yang paling dekat dengan tempat menyimpannya.

Dua akibat yang dicegah:
  1. Menyetujui ulang menimpa `approvedBy` dan `approvedAt` — jejak siapa
     yang benar-benar menyetujui hilang, padahal blok tanda tangan pada
     lembar yang dipegang vendor memuat nama penyetuju pertama.
  2. Menghapus dokumen yang sudah disetujui membuat lembar yang beredar
     tidak punya padanan sama sekali di sistem.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMBER = open(
    os.path.join(AKAR, "repository", "purchase_order_repository.py")
).read()


def _blok(nama: str) -> str:
    """
    Isi satu fungsi, sampai fungsi berikutnya ATAU akhir berkas.

    Tanpa cadangan akhir berkas, fungsi terakhir tidak pernah terbaca — dan
    ujinya gagal seolah penjagaannya tidak ada, padahal ada. `soft_delete`
    kebetulan fungsi terakhir, dan itulah yang terjadi.
    """
    i = SUMBER.index(f"async def {nama}(")
    j = SUMBER.find("async def ", i + 10)
    return SUMBER[i:] if j == -1 else SUMBER[i:j]


def test_approve_menolak_yang_sudah_disetujui():
    b = _blok("approve")
    assert "already approved" in b
    assert '"status": 409' in b or "status\": 409" in b


def test_approve_menolak_yang_sudah_dihapus():
    """Menyetujui dokumen terhapus menghasilkan keadaan yang tidak berarti."""
    assert "has been deleted" in _blok("approve")


def test_delete_menolak_yang_sudah_disetujui():
    b = _blok("soft_delete")
    assert "cannot be deleted" in b


def test_keduanya_menyaring_ulang_di_perintahnya():
    """
    Syaratnya diulang pada `UPDATE`, bukan hanya diperiksa lebih dulu.

    Dua orang yang menekan pada saat hampir bersamaan dapat lolos
    pemeriksaan yang sama; syarat pada perintahnya hanya benar untuk yang
    pertama sampai.
    """
    for nama in ("approve", "soft_delete"):
        b = _blok(nama)
        assert "isApproved == False" in b, nama
