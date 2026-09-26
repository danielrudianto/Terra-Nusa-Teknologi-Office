"""
"TERTAGIH" PADA DAFTAR PROYEK HANYA MENGHITUNG FAKTUR YANG SUDAH TERBIT.

Kolomnya bernama "yang SUDAH difakturkan ke klien" dan menjadi pembanding
biaya pada layar margin, dasbor proyek, dan laporan proyek. Faktur yang
belum disetujui BELUM terbit — belum sampai ke klien, dan klien belum
berutang apa pun karenanya.

ARAHNYA YANG BERBAHAYA, dan itu sebabnya uji ini ada.

Kueri yang sama sengaja memasukkan DRAF PEMBELIAN ke sisi biaya —
konservatif, karena biaya yang belum tercatat yang paling menyesatkan.
Memasukkan faktur draf ke sisi PENDAPATAN adalah kebalikannya: ia
membesarkan yang masuk, dan membuat proyek tampak lebih sehat daripada
kenyataannya tepat pada angka yang dibaca untuk memutuskan lanjut atau
berhenti.

Seluruh penghitung lain — laba rugi, KPI, arus kas proyek, status
keuangan — sudah menyaring `isApprove`. Daftar proyek tertinggal sendirian,
sehingga dua layar dapat menyebut dua angka "tertagih" yang berbeda untuk
proyek yang sama tanpa satu pun terlihat salah.
"""

import re

import pytest

from repository.project_repository import ProjectRepository

MODUL = "repository.project_repository"


def _sql(db, metode="fetch_all"):
    return [" ".join(str(q).split()) for m, q in db.calls if m == metode]


def _subkueri_tertagih(sql: str) -> str:
    """Potong subkueri `tertagih` saja, supaya `isApprove` milik tabel lain
    tidak ikut terbaca sebagai bukti."""
    m = re.search(
        r"SELECT projectName, SUM\(dpp\) AS tertagih FROM sales_invoices(.*?)GROUP BY",
        sql,
        re.S,
    )
    assert m, "subkueri tertagih tidak ditemukan — bentuknya berubah"
    return m.group(1)


@pytest.mark.asyncio
async def test_tertagih_menyaring_faktur_yang_belum_disetujui(fake_db):
    db = fake_db(MODUL)
    db.queue("fetch_val", 0)
    db.queue("fetch_all", [])
    await ProjectRepository.ringkasan_margin()

    sql = next(s for s in _sql(db) if "tertagih" in s)
    bagian = _subkueri_tertagih(sql)
    assert "isDelete = 0" in bagian
    assert "isApprove = 1" in bagian, bagian


@pytest.mark.asyncio
async def test_sisi_BIAYA_tetap_memasukkan_draf(fake_db):
    """
    Penjaga arah sebaliknya.

    Asimetrinya DISENGAJA: biaya dihitung lebih awal, pendapatan dihitung
    lebih akhir. Menyamakan keduanya — membuang draf dari biaya "supaya
    konsisten" — menghapus justru penjagaan yang paling berguna di layar
    itu, dan proyek yang tagihannya belum masuk semua akan tampak untung.
    """
    db = fake_db(MODUL)
    db.queue("fetch_val", 0)
    db.queue("fetch_all", [])
    await ProjectRepository.ringkasan_margin()

    sql = next(s for s in _sql(db) if "tertagih" in s)
    assert "purchase_draft" in sql, "draf pembelian hilang dari sisi biaya"
    assert "AS draft" in sql
