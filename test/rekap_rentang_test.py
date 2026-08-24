"""
Rentang tanggal pada rekap purchase order.

Staf procurement kerap diminta "pembelian minggu ini apa saja" — dan rekap
yang selalu memuat SELURUH riwayat proyek tidak menjawab itu.

Dua hal yang dijaga, dan yang kedua paling mudah meleset:

  1. rentangnya PILIHAN — tanpa tanggal, rekapnya tetap memuat semuanya
     seperti sebelum fitur ini ada;
  2. batasnya INKLUSIF — "sampai 31 Agustus" termasuk dokumen tanggal 31.

Batas atas yang eksklusif menghilangkan dokumen hari terakhir tanpa ada yang
menyadari: jumlahnya tetap masuk akal, dan yang membacanya tidak punya
pembanding.

Diperiksa dari kueri yang BENAR-BENAR disusun, memakai basis data tiruan.
"""

import asyncio

from repository.purchase_order_repository import PurchaseOrderRepository

MODUL = "repository.purchase_order_repository"


def _jalankan(fake_db, **kwargs):
    db = fake_db(MODUL)
    # Dokumen kosong menghentikan langkah berikutnya; cukup untuk memeriksa
    # kueri pertama, yang memang satu-satunya yang menyaring tanggal.
    db.queue("fetch_all", [])
    asyncio.run(PurchaseOrderRepository.rekap_proyek("R501", **kwargs))
    return str(db.last_query("fetch_all")), db


def test_tanpa_tanggal_tidak_menyaring_apa_pun(fake_db):
    """Perilaku lama harus utuh: rekap tanpa tanggal memuat seluruh riwayat."""
    kueri, _ = _jalankan(fake_db)

    assert "po.date >=" not in kueri
    assert "po.date <=" not in kueri
    assert "po.projectName = :proyek" in kueri


def test_rentang_dipakai_bila_diisi(fake_db):
    kueri, db = _jalankan(fake_db, dari="2026-08-01", sampai="2026-08-31")

    assert "po.date >= :dari" in kueri
    assert "po.date <= :sampai" in kueri

    nilai = db.last_values("fetch_all")
    assert nilai["dari"] == "2026-08-01"
    assert nilai["sampai"] == "2026-08-31"
    assert nilai["proyek"] == "R501"


def test_batas_atas_INKLUSIF():
    """
    `<=`, bukan `<`.

    `po.date` bertipe DATE, sehingga `<=` sudah mencakup seluruh hari itu.
    Memakai `<` menghilangkan dokumen tanggal terakhir — dan jumlahnya tetap
    masuk akal, sehingga tidak ada yang menyadarinya.
    """
    import inspect

    sumber = inspect.getsource(PurchaseOrderRepository.rekap_proyek)
    assert "po.date <= :sampai" in sumber
    assert "po.date < :sampai" not in sumber


def test_hanya_salah_satu_batas_juga_boleh(fake_db):
    """"Sejak 1 Agustus" tanpa batas akhir adalah permintaan yang wajar."""
    kueri, _ = _jalankan(fake_db, dari="2026-08-01")
    assert "po.date >= :dari" in kueri
    assert "po.date <= :sampai" not in kueri


def test_dokumen_terhapus_tetap_dikecualikan(fake_db):
    """Penyaring tanggal tidak boleh menggeser syarat yang sudah ada."""
    kueri, _ = _jalankan(fake_db, dari="2026-08-01", sampai="2026-08-31")
    assert "po.isDelete = 0" in kueri
    assert "po.projectName = :proyek" in kueri
