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


def test_delete_menjaga_yang_sudah_disetujui():
    """
    Aturannya BERUBAH, penjagaannya tidak hilang.

    Semula dokumen yang sudah disetujui ditolak siapa pun — 409 tanpa
    kecuali. Kini ia hanya boleh dihapus PEMILIK, atas keputusan pemilik
    sendiri: kadang dokumen memang keliru sejak awal dan harus benar-benar
    hilang.

    Yang diperiksa di sini keberadaan penjagaannya, bukan bunyi pesannya.
    Perinciannya — level berapa, apa yang tertulis, apa yang terjadi pada
    perintahnya — diuji lewat perilaku di `hapus_po_disetujui_test.py`.
    """
    b = _blok("soft_delete")
    assert "boleh_menghapus_yang_disetujui" in b
    assert "PO_DELETE_APPROVED_FORBIDDEN" in b


def test_keduanya_menyaring_ulang_di_perintahnya():
    """
    Syaratnya diulang pada `UPDATE`, bukan hanya diperiksa lebih dulu.

    Dua orang yang menekan pada saat hampir bersamaan dapat lolos
    pemeriksaan yang sama; syarat pada perintahnya hanya benar untuk yang
    pertama sampai.

    Pada `soft_delete` saringan itu kini BERSYARAT — hanya bagi dokumen yang
    belum disetujui. Memasangnya juga pada penghapusan oleh pemilik membuat
    perintahnya tidak mencocokkan satu baris pun, dan `execute` yang
    mengubah nol baris tidak melempar galat: layar mengabarkan berhasil atas
    dokumen yang masih utuh. Keadaan itu dijaga perilakunya di
    `hapus_po_disetujui_test.py`.
    """
    for nama in ("approve", "soft_delete"):
        b = _blok(nama)
        assert "isApproved == False" in b, nama

    assert "if not disetujui:" in _blok("soft_delete")
