"""
Mengubah pembelian dijaga VERSI barisnya.

Dua orang membuka pembelian yang sama; yang pertama menyimpan, lalu yang
kedua menyimpan formulir lamanya. Sebelumnya yang kedua menang diam-diam dan
pekerjaan yang pertama hilang. Kini penyimpanan kedua ditolak 409.
"""

import pytest

from repository.purchase_repository import PurchaseRepository

MODUL = "repository.purchase_repository"


def _sebelum():
    return {"id": 5, "isDelete": False, "invoiceName": "INV-1", "rowVersion": 3}


@pytest.fixture()
def jejak(monkeypatch):
    import repository.audit_log_repository as al

    catat = []

    async def rekam(**k):
        catat.append(k)

    monkeypatch.setattr(al.AuditLogRepository, "record", staticmethod(rekam))
    return catat


def _update(db):
    return [q for m, q in db.calls if m == "execute" and str(q).startswith("UPDATE purchases")]


@pytest.mark.asyncio
async def test_versi_masuk_ke_WHERE(fake_db, jejak):
    db = fake_db(MODUL)
    db.queue("fetch_one", _sebelum(), _sebelum())
    db.queue("execute", 1)

    await PurchaseRepository.update(5, {"invoiceName": "INV-2", "rowVersion": 7}, 1)

    q = _update(db)
    assert q, "UPDATE tidak dikirim"
    sql = str(q[0])
    where = sql[sql.index("WHERE"):]
    assert '"rowVersion"' in where or "rowVersion" in where, where
    # Nilai 7 dipilih supaya tidak tertukar dengan `+ 1` pada SET.
    assert 7 in q[0].compile().params.values(), q[0].compile().params


@pytest.mark.asyncio
async def test_didahului_orang_lain_dijawab_409(fake_db, jejak):
    db = fake_db(MODUL)
    # sebelum; UPDATE mengenai 0 baris; barisnya MASIH ADA -> konflik
    db.queue("fetch_one", _sebelum(), {"id": 5})
    db.queue("execute", 0)

    hasil = await PurchaseRepository.update(5, {"invoiceName": "INV-2", "rowVersion": 2}, 1)

    assert hasil.get("status") == 409
    assert "diubah orang lain" in hasil.get("error", "")
    assert not jejak, "perubahan yang ditolak ikut dicatat di jejak audit"


@pytest.mark.asyncio
async def test_rowVersion_tidak_dapat_dipaksa_dari_muatan(fake_db, jejak):
    """Versi di muatan adalah SYARAT, bukan nilai yang ditulis."""
    db = fake_db(MODUL)
    db.queue("fetch_one", _sebelum(), _sebelum())
    db.queue("execute", 1)

    await PurchaseRepository.update(5, {"invoiceName": "X", "rowVersion": 999}, 1)

    sql = str(_update(db)[0])
    set_ = sql[sql.index("SET"):sql.index("WHERE")]
    assert "rowVersion" in set_ and "+" in set_, set_  # rowVersion = rowVersion + 1
