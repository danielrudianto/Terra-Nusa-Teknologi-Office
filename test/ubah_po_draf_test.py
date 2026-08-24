"""
Purchase order yang belum disetujui dapat diubah; yang sudah, tidak.

Draf memang belum mengikat — cap DRAFT pada cetakannya menyatakan itu.
Membetulkannya bukan pemalsuan melainkan gunanya tahap draf. Tanpa jalur ini
yang tersisa hanya dua pilihan buruk: menghapus lalu membuat ulang, yang
membuat deret nomor proyek berlubang; atau menerbitkan yang salah lalu
diadendum, yang memakai dokumen resmi untuk membetulkan sesuatu yang belum
pernah terbit.

Tiga batasan yang menjadikannya aman, dan ketiganya diperiksa di sini.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _blok(berkas: str, nama: str) -> str:
    s = open(os.path.join(AKAR, berkas)).read()
    i = s.index(f"async def {nama}(")
    j = s.find("async def ", i + 10)
    return s[i:] if j == -1 else s[i:j]


def test_ditolak_bila_sudah_disetujui():
    """
    Diperiksa di REPOSITORY, bukan hanya di rute.

    Aturan ini tentang dokumennya, bukan tentang salah satu jalur menuju
    dokumen itu; menaruhnya di satu tempat membuat jalur lain tidak dapat
    melewatinya.
    """
    b = _blok("repository/purchase_order_repository.py", "update")
    assert "isApproved" in b
    assert "approved" in b
    assert "ErrorCode.FORBIDDEN" in b


def test_kolom_identitas_terkunci():
    """
    Nomor, pemasok, proyek, dan jenis menyusun nomor dokumennya sendiri.

    Mengubah pemasok bukan koreksi melainkan dokumen lain; yang seperti itu
    dibatalkan lalu dibuat baru.
    """
    b = _blok("repository/purchase_order_repository.py", "update")
    for kolom in ("name", "number", "supplierID", "projectName", "purchaseType"):
        assert f'"{kolom}"' in b, f"{kolom} tidak terkunci"


def test_hanya_pembuat_atau_level_empat():
    """
    Aturannya DIPANGGIL, bukan ditulis ulang di sini.

    Percobaan pertama memeriksa apakah teks ">= 4" muncul di badan fungsinya.
    Itu lulus selama angkanya kebetulan tertulis — dan gagal begitu aturannya
    dipindahkan ke `utils/permission.py`, meskipun perilakunya tidak berubah
    sedikit pun. Perilakunya sendiri diuji di `ubah_po_pemeriksa_test.py`.
    """
    b = _blok("controllers/purchase_order_controller.py", "update_purchase_order")
    assert "createdBy" in b
    assert "boleh_mengubah_purchase_order" in b
    assert "isChecked" in b
    # Kode TERSENDIRI, bukan `FORBIDDEN` biasa.
    #
    # `FORBIDDEN` diterjemahkan layar menjadi "Anda tidak memiliki akses untuk
    # tindakan ini" — benar, tetapi tidak menyebut apa pun yang dapat
    # ditindaklanjuti. Yang membacanya perlu tahu bahwa dokumen ini hanya
    # dapat diubah PEMBUATNYA, sehingga ia menghubungi orangnya alih-alih
    # meminta izinnya dinaikkan.
    assert "ErrorCode.PO_EDIT_FORBIDDEN" in b


def test_revisi_dinaikkan():
    """
    Bila draf lama sempat tercetak dan sampai ke vendor, nomor revisi itulah
    yang membedakan mana yang lebih baru.
    """
    b = _blok("repository/purchase_order_repository.py", "update")
    assert "revision=purchase_orders_table.c.revision + 1" in b


def test_ada_rutenya():
    """
    Fungsinya sempat ada TANPA rute sama sekali, sehingga tidak pernah dapat
    dipakai — dan itu tidak terlihat sebagai kesalahan pada siapa pun.
    """
    s = open(os.path.join(AKAR, "routes", "purchase_order_routes.py")).read()
    assert "@router.put" in s
    assert "update_purchase_order" in s
