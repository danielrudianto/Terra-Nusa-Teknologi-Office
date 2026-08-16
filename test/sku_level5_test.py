"""
SKU barang hanya dapat diubah oleh level 5.

Kode ini penyebut yang dipegang seluruh dokumen — purchase order, pembelian,
dan rekap semuanya menyebutnya. Mengubahnya bukan pembetulan biasa seperti
memperbaiki deskripsi atau merek.

Izin `master_item:update` sendiri terbuka sampai level 3, dan itu memang
tepat untuk bidang lainnya. Yang membedakan SKU karena itu bukan izin per
modul melainkan level itu sendiri.

Diperiksa di SERVER. Mengunci isiannya di layar tidak cukup: muatan
permintaan dapat disusun sendiri oleh siapa pun yang membuka Network tab.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERKAS = os.path.join(AKAR, 'routes', 'master_item_routes.py')


def _blok_put() -> str:
    s = open(BERKAS).read()
    i = s.index('@router.put("/{item_id}")')
    j = s.find('@router.', i + 10)
    return s[i:] if j == -1 else s[i:j]


def test_sku_dijaga_level():
    b = _blok_put()
    assert 'payload.get("sku")' in b
    assert 'level < 5' in b


def test_sku_dibuang_bukan_ditolak():
    """
    Permintaannya tetap berjalan; hanya SKU-nya yang tidak ikut.

    Menolak seluruh permintaan akan membuat yang membetulkan deskripsi gagal
    hanya karena formulirnya kebetulan menyertakan SKU yang tidak berubah.
    """
    b = _blok_put()
    assert 'payload.pop("sku", None)' in b


def test_memakai_nama_kolom_yang_benar():
    """
    `authenticationLevel`, bukan `accessLevel`.

    Nama yang keliru membuat pembacaan melempar, dan penjagaannya jatuh ke
    level 1 — yang kebetulan aman di sini, tetapi karena alasan yang salah.
    """
    b = _blok_put()
    assert 'authenticationLevel' in b


def test_level_tak_terbaca_dianggap_rendah():
    """
    Bila levelnya gagal dibaca, yang berlaku level 1 — bukan lolos.
    """
    b = _blok_put()
    assert 'except Exception:' in b
    assert 'level = 1' in b
