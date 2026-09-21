"""
Mencari di daftar draf pembelian TIDAK boleh memunculkan draf yang dihapus.

Syarat `isDelete = false` dulu ditambahkan ke daftar OR milik pencarian.
Tanpa kata kunci hasilnya kebetulan benar; dengan kata kunci ia ter-OR-kan
bersama kecocokan nama, dan draf yang sudah dihapus muncul di tab tertunda
asal namanya cocok — tanpa galat apa pun.

Kuerinya yang SUNGGUHAN ditangkap lalu dijalankan pada SQLite berisi satu
draf aktif dan satu draf terhapus dengan nama yang sama.
"""

import asyncio
from datetime import date, datetime

import pytest
from sqlalchemy import MetaData, create_engine

import models.purchase_draft_model as m
import models.user_model  # noqa: F401  (kunci asing `createdBy` menunjuk ke sini)


class _Tangkap:
    def __init__(self):
        self.q = []

    async def fetch_all(self, q, *a):
        self.q.append(q)
        return []

    async def fetch_val(self, q, *a):
        self.q.append(q)
        return 0


def _tabel_perlu():
    """purchase_draft, suppliers, dan tabel yang dirujuk kunci asingnya."""
    tabel = {m.purchase_draft_table, m.suppliers_table}
    antre = list(tabel)
    while antre:
        t = antre.pop()
        for fk in t.foreign_keys:
            r = fk.column.table
            if r not in tabel:
                tabel.add(r)
                antre.append(r)
    return tabel


@pytest.fixture()
def mesin():
    e = create_engine("sqlite://")
    md = MetaData()
    for t in _tabel_perlu():
        t.to_metadata(md)
    md.create_all(e)
    return e


def _wajib(tabel, **isi):
    """
    Nilai untuk setiap kolom NOT NULL tanpa bawaan, ditimpa `isi`.

    Kolom wajib diisi otomatis menurut tipenya supaya uji ini tidak patah
    setiap kali tabelnya bertambah kolom — dan TIDAK dilewati diam-diam
    bila gagal diisi: uji yang dilewati sama dengan uji yang tidak ada.
    """
    from sqlalchemy import Boolean, Date, DateTime, Float, Integer, Numeric

    nilai = {}
    for k in tabel.columns:
        if k.nullable or k.server_default is not None or k.default is not None:
            continue
        if k.primary_key and k.autoincrement:
            continue
        t = k.type
        if isinstance(t, Boolean):
            nilai[k.name] = False
        elif isinstance(t, DateTime):
            nilai[k.name] = datetime(2026, 9, 1)
        elif isinstance(t, Date):
            nilai[k.name] = date(2026, 9, 1)
        elif isinstance(t, (Integer, Float, Numeric)):
            nilai[k.name] = 1
        else:
            nilai[k.name] = "-"
    nilai.update(isi)
    return nilai


def _isi(mesin):
    with mesin.begin() as c:
        c.execute(
            m.suppliers_table.insert().values(
                **_wajib(m.suppliers_table, id=1, name="Toko Semen Jaya")
            )
        )
        for i, hapus in ((1, False), (2, True)):
            c.execute(
                m.purchase_draft_table.insert().values(
                    **_wajib(
                        m.purchase_draft_table,
                        id=i,
                        supplierID=1,
                        purchaseOrderName=f"Semen draf {i}",
                        isDelete=hapus,
                        convertedAt=None,
                    )
                )
            )


def _jalankan(mesin, isPending, isApproved, kata):
    db = _Tangkap()
    lama = m.database
    m.database = db
    try:
        asyncio.run(
            m.PurchaseDraft.get_purchase_draft(1, 50, isPending, isApproved, "date", "desc", kata)
        )
    finally:
        m.database = lama
    with mesin.connect() as c:
        return sorted(r.id for r in c.execute(db.q[0]))


def test_cari_di_tab_tertunda_tidak_memunculkan_yang_dihapus(mesin):
    _isi(mesin)
    assert _jalankan(mesin, True, False, "semen") == [1]


def test_tanpa_kata_kunci_tetap_benar(mesin):
    _isi(mesin)
    assert _jalankan(mesin, True, False, "") == [1]


def test_kata_kunci_tetap_menyaring(mesin):
    _isi(mesin)
    assert _jalankan(mesin, True, False, "tidak-ada-yang-cocok") == []
