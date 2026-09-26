"""
Mengubah tender dijaga VERSI barisnya — dua orang yang menyunting tender
yang sama tidak lagi saling menimpa diam-diam; yang kedua dijawab 409.
"""

import pytest

from repository.tender_repository import TenderRepository

MODUL = "repository.tender_repository"


@pytest.fixture()
def jejak(monkeypatch):
    import repository.audit_log_repository as al

    catat = []

    async def rekam(**k):
        catat.append(k)

    monkeypatch.setattr(al.AuditLogRepository, "record", staticmethod(rekam))
    return catat


@pytest.fixture()
def baris_ditulis(monkeypatch):
    tulis = []

    async def palsu(tender_id, baris):
        tulis.append(baris)

    monkeypatch.setattr(TenderRepository, "_tulis_baris", staticmethod(palsu))
    return tulis


def _update(db):
    return [q for m, q in db.calls if m == "execute" and str(q).startswith("UPDATE tenders")]


@pytest.mark.asyncio
async def test_versi_masuk_ke_WHERE(fake_db, jejak, baris_ditulis):
    db = fake_db(MODUL)
    db.queue("execute", 1)

    hasil = await TenderRepository.ubah(5, {"name": "Baru"}, None, 1, versi=7)

    assert hasil == {"id": 5}
    q = _update(db)[0]
    sql = str(q)
    assert "rowVersion" in sql[sql.index("WHERE"):]
    assert 7 in q.compile().params.values()


@pytest.mark.asyncio
async def test_didahului_orang_lain_dijawab_409_baris_tidak_ditulis(
    fake_db, jejak, baris_ditulis
):
    db = fake_db(MODUL)
    db.queue("execute", 0)
    db.queue("fetch_one", {"id": 5})

    hasil = await TenderRepository.ubah(5, {"name": "Baru"}, [{"name": "x"}], 1, versi=2)

    assert hasil.get("status") == 409
    assert not baris_ditulis, "baris permintaan tetap ditimpa walau konflik"
    assert not jejak


@pytest.mark.asyncio
async def test_ubah_baris_saja_tetap_menaikkan_versi(fake_db, jejak, baris_ditulis):
    db = fake_db(MODUL)
    db.queue("execute", 1)

    await TenderRepository.ubah(5, {}, [{"name": "x"}], 1, versi=3)

    sql = str(_update(db)[0])
    assert "rowVersion" in sql[sql.index("SET"):sql.index("WHERE")]
    assert baris_ditulis == [[{"name": "x"}]]


@pytest.mark.asyncio
async def test_controller_meneruskan_rowVersion(monkeypatch):
    from controllers.tender_controller import TenderController

    async def ambil(_id):
        return {"id": 5, "status": "draft", "items": []}

    diterima = {}

    async def ubah(tid, nilai, baris, uid, versi=None):
        diterima.update(nilai=nilai, versi=versi)
        return {"id": tid}

    monkeypatch.setattr(TenderRepository, "ambil", staticmethod(ambil))
    monkeypatch.setattr(TenderRepository, "ubah", staticmethod(ubah))
    await TenderController.ubah(5, {"name": "A", "rowVersion": 4}, 1)
    assert diterima == {"nilai": {"name": "A"}, "versi": 4}
