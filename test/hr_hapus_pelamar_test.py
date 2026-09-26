"""
Hapus pelamar seutuhnya, dan pulihkan.

KENAPA PENGUJIAN INI ADA

Ember "Dihapus" di menu samping menghitung `isDelete = 1`, dan sebelum ini
TIDAK ADA tindakan yang menyetelnya. "Hapus hasil & ulangi" hanya membuang
jawaban. Embernya terpasang, lencananya tampil, dan angkanya nol selamanya.
Ditemukan pemakainya, bukan satu pun uji — karena memang tidak ada yang
salah dengan apa pun yang sudah ada; yang kurang adalah tindakannya.

CARA MENGUJINYA

Pernyataan UPDATE yang benar-benar dibentuk repository DITANGKAP, lalu
DIJALANKAN pada SQLite di memori berisi satu pelamar aktif dan satu yang
sudah terhapus. Yang diperiksa baris mana yang berubah — bukan teks
kuerinya. `isDelete == True` yang tertulis `isDelete == False` tetap
berupa perbandingan yang sah dan tetap muncul di teks kueri.
"""

from datetime import datetime as dt

import pytest
from sqlalchemy import create_engine, select

from models.hr_recruitment_model import hr_candidates_table, hr_tests_table
from models.user_model import users_table
from repository.hr_recruitment_repository import (
    HrRecruitmentRepository,
    _syarat_ember,
)

MODUL = "repository.hr_recruitment_repository"
AKTIF, TERHAPUS = 1, 2


@pytest.fixture()
def mesin():
    e = create_engine("sqlite://")
    for t in (users_table, hr_tests_table, hr_candidates_table):
        t.create(e, checkfirst=True)
    w = dt(2026, 9, 1)
    with e.begin() as c:
        c.execute(
            hr_candidates_table.insert(),
            [
                {
                    "id": i,
                    "testID": 1,
                    "name": f"P{i}",
                    "token": f"t{i}",
                    "expiresAt": dt(2026, 12, 31),
                    "status": "selesai",
                    "submittedAt": w,
                    "isDelete": hapus,
                    "createdAt": w,
                    "createdBy": 1,
                }
                for i, hapus in ((AKTIF, 0), (TERHAPUS, 1))
            ],
        )
    return e


@pytest.fixture()
def jejak(monkeypatch):
    """Tangkap catatan audit tanpa menyentuh tabelnya."""
    import repository.audit_log_repository as al

    catatan = []

    async def rekam(**k):
        catatan.append(k)

    monkeypatch.setattr(al.AuditLogRepository, "record", staticmethod(rekam))
    return catatan


def _update_terakhir(db):
    for m, q in reversed(db.calls):
        if m == "execute" and str(q).startswith("UPDATE hr_candidates"):
            return q
    return None


def _jalankan(mesin, q) -> int:
    with mesin.begin() as c:
        return c.execute(q).rowcount


def _hapus(mesin, i) -> int:
    with mesin.connect() as c:
        return c.execute(
            select(hr_candidates_table.c.isDelete).where(
                hr_candidates_table.c.id == i
            )
        ).scalar()


# ---------------------------------------------------------------------
# Hapus
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hapus_mengenai_yang_aktif(fake_db, mesin, jejak):
    db = fake_db(MODUL)
    db.queue("execute", 1)
    await HrRecruitmentRepository.hapus_pelamar(AKTIF, 7)

    q = _update_terakhir(db)
    assert q is not None, "tidak ada UPDATE yang dikirim"
    assert _jalankan(mesin, q) == 1
    assert _hapus(mesin, AKTIF) == 1


@pytest.mark.asyncio
async def test_hapus_TIDAK_mengenai_yang_sudah_terhapus(fake_db, mesin, jejak):
    """Syaratnya di dalam UPDATE — penghapusan kedua mengenai nol baris."""
    db = fake_db(MODUL)
    db.queue("execute", 1)
    await HrRecruitmentRepository.hapus_pelamar(TERHAPUS, 7)
    assert _jalankan(mesin, _update_terakhir(db)) == 0


@pytest.mark.asyncio
async def test_hapus_kedua_dijawab_404_tanpa_jejak_audit(fake_db, jejak):
    db = fake_db(MODUL)
    db.queue("execute", 0)  # tidak ada baris yang berubah
    hasil = await HrRecruitmentRepository.hapus_pelamar(AKTIF, 7)
    assert isinstance(hasil, dict) and hasil.get("status") == 404
    assert not jejak, "penghapusan yang tidak terjadi ikut dicatat"


@pytest.mark.asyncio
async def test_hapus_dicatat_dengan_pelakunya(fake_db, jejak):
    db = fake_db(MODUL)
    db.queue("execute", 1)
    await HrRecruitmentRepository.hapus_pelamar(AKTIF, 7)
    assert jejak and jejak[0]["action"] == "hapus_pelamar"
    assert jejak[0]["userID"] == 7
    assert jejak[0]["entityID"] == AKTIF


@pytest.mark.asyncio
async def test_hapus_TIDAK_membuang_jawaban(fake_db, jejak):
    """Lunak: jawaban tetap ada supaya pemulihan mengembalikan lembarnya utuh."""
    db = fake_db(MODUL)
    db.queue("execute", 1)
    await HrRecruitmentRepository.hapus_pelamar(AKTIF, 7)
    perintah = [str(q) for m, q in db.calls if m == "execute"]
    assert not any(p.startswith("DELETE") for p in perintah), perintah


@pytest.mark.asyncio
async def test_setelah_dihapus_pindah_ke_ember_dihapus(fake_db, mesin, jejak):
    db = fake_db(MODUL)
    db.queue("execute", 1)
    await HrRecruitmentRepository.hapus_pelamar(AKTIF, 7)
    _jalankan(mesin, _update_terakhir(db))

    with mesin.connect() as c:
        terbit = {r[0] for r in c.execute(
            select(hr_candidates_table.c.id).where(*_syarat_ember("terbit")))}
        dihapus = {r[0] for r in c.execute(
            select(hr_candidates_table.c.id).where(*_syarat_ember("dihapus")))}
    assert AKTIF not in terbit
    assert AKTIF in dihapus


# ---------------------------------------------------------------------
# Pulihkan
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pulihkan_mengenai_yang_terhapus(fake_db, mesin, jejak):
    db = fake_db(MODUL)
    db.queue("execute", 1)
    await HrRecruitmentRepository.pulihkan_pelamar(TERHAPUS, 7)
    assert _jalankan(mesin, _update_terakhir(db)) == 1
    assert _hapus(mesin, TERHAPUS) == 0


@pytest.mark.asyncio
async def test_pulihkan_TIDAK_mengenai_yang_aktif(fake_db, mesin, jejak):
    db = fake_db(MODUL)
    db.queue("execute", 1)
    await HrRecruitmentRepository.pulihkan_pelamar(AKTIF, 7)
    assert _jalankan(mesin, _update_terakhir(db)) == 0


@pytest.mark.asyncio
async def test_pulihkan_yang_tidak_terhapus_dijawab_404(fake_db, jejak):
    db = fake_db(MODUL)
    db.queue("execute", 0)
    hasil = await HrRecruitmentRepository.pulihkan_pelamar(AKTIF, 7)
    assert isinstance(hasil, dict) and hasil.get("status") == 404
    assert not jejak


@pytest.mark.asyncio
async def test_pulihkan_tidak_memperpanjang_tautan(fake_db, jejak):
    """Memulihkan bukan menerbitkan ulang: `expiresAt` tidak disentuh."""
    db = fake_db(MODUL)
    db.queue("execute", 1)
    await HrRecruitmentRepository.pulihkan_pelamar(TERHAPUS, 7)
    q = _update_terakhir(db)
    assert "expiresAt" not in str(q).split("SET", 1)[1].split("WHERE", 1)[0]


# ---------------------------------------------------------------------
# Rute: dijaga `delete`, keduanya.
# ---------------------------------------------------------------------


def _penjaga(nama_fungsi):
    import inspect

    import routes.hr_recruitment_routes as r

    sumber = inspect.getsource(getattr(r, nama_fungsi))
    return sumber


def test_rute_hapus_dijaga_delete():
    assert 'require("hr_recruitment", "delete")' in _penjaga("hapus_pelamar")


def test_rute_pulihkan_dijaga_delete_BUKAN_update():
    """Yang boleh membatalkan keputusan harus sama dengan yang mengambilnya."""
    s = _penjaga("pulihkan_pelamar")
    assert 'require("hr_recruitment", "delete")' in s
    assert 'require("hr_recruitment", "update")' not in s
