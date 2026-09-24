"""
DAFTAR CoP — penyaring rentang tanggal, dan dua kolom yang kini dapat
diurutkan.

Yang dijaga di sini semuanya gagal dengan DIAM:

  * tanggal yang bukan tanggal. Ia masuk sebagai parameter, jadi ia tidak
    dapat menyuntik SQL — tetapi MySQL membandingkan `DATE` dengan teks
    yang bukan tanggal sebagai `NULL`, dan SELURUH baris rontok tanpa satu
    pun galat. Layar menjawab "belum ada CoP" untuk daftar berisi ratusan
    dokumen.

  * penyaring tanggal yang tidak ikut ke HITUNGANNYA. Isinya tersaring,
    jumlahnya tidak — dan pemenggal halaman menjanjikan halaman keempat
    yang isinya kosong.

  * "spk" dan "periode" sebagai dasar pengurutan. Nama kolom yang tidak
    dikenali DIABAIKAN, bukan ditolak; kepala kolom yang baru akan tampak
    bekerja sementara daftarnya diam-diam tetap terurut menurut tanggal.
"""

import pytest

from repository.certificate_of_payment_repository import (
    CertificateOfPaymentRepository as Repo,
    _tanggal_saring,
)

MODUL = "repository.certificate_of_payment_repository"


def _sql(db, metode):
    return [" ".join(str(q).split()) for m, q in db.calls if m == metode]


def _nilai(db, metode):
    return [v for m, v in db.calls_values if m == metode]


async def _panggil(db, **kw):
    db.queue("fetch_val", 0)
    db.queue("fetch_all", [])
    return await Repo.get_all(**kw)


# --------------------------------------------------------------------- #
# penyaring tanggal
# --------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_rentang_masuk_ke_daftar_dan_ke_hitungannya(fake_db):
    db = fake_db(MODUL)
    await _panggil(db, dari="2026-09-01", sampai="2026-09-30")

    daftar = _sql(db, "fetch_all")[0]
    hitung = _sql(db, "fetch_val")[0]
    for sql in (daftar, hitung):
        assert "c.date >= :dari" in sql, sql
        assert "c.date <= :sampai" in sql, sql

    # Nilainya benar-benar terikat, bukan disambung ke dalam teks SQL.
    v = _nilai(db, "fetch_all")[0]
    assert v["dari"] == "2026-09-01"
    assert v["sampai"] == "2026-09-30"


@pytest.mark.asyncio
async def test_satu_ujung_saja_tetap_menyaring(fake_db):
    db = fake_db(MODUL)
    await _panggil(db, dari="2026-09-01")
    sql = _sql(db, "fetch_all")[0]
    assert "c.date >= :dari" in sql
    assert ":sampai" not in sql

    db2 = fake_db(MODUL)
    await _panggil(db2, sampai="2026-09-30")
    sql2 = _sql(db2, "fetch_all")[0]
    assert "c.date <= :sampai" in sql2
    assert ":dari" not in sql2


@pytest.mark.asyncio
async def test_tanpa_rentang_tidak_menyaring_apa_pun(fake_db):
    db = fake_db(MODUL)
    await _panggil(db)
    sql = _sql(db, "fetch_all")[0]
    assert ":dari" not in sql and ":sampai" not in sql


@pytest.mark.asyncio
async def test_tanggal_ngawur_DIABAIKAN_bukan_diteruskan(fake_db):
    """
    Inilah yang paling berbahaya: diteruskan apa adanya, daftarnya kosong
    total dan tidak ada apa pun yang menyebut sebabnya.
    """
    db = fake_db(MODUL)
    hasil = await _panggil(db, dari="bukan tanggal", sampai="30/09/2026")
    assert "error" not in hasil
    sql = _sql(db, "fetch_all")[0]
    assert ":dari" not in sql and ":sampai" not in sql


@pytest.mark.asyncio
async def test_rentang_hidup_bersama_keping_DIHAPUS(fake_db):
    """
    Penyaring tanggal tidak boleh melonggarkan penyaring terhapus, dan
    sebaliknya. Keduanya berdiri sendiri dan harus bertumpuk.
    """
    db = fake_db(MODUL)
    await _panggil(db, keadaan="dihapus", dari="2026-09-01")
    sql = _sql(db, "fetch_all")[0]
    assert "c.isDelete = 1" in sql
    assert "c.date >= :dari" in sql

    db2 = fake_db(MODUL)
    await _panggil(db2, keadaan="draft", dari="2026-09-01")
    sql2 = _sql(db2, "fetch_all")[0]
    assert "c.isDelete = 0" in sql2
    assert "c.isBapApproved = 0" in sql2
    assert "c.date >= :dari" in sql2


def test_penolong_tanggal_menerima_bentuk_yang_dikirim_peramban():
    assert _tanggal_saring("2026-09-01") == "2026-09-01"
    # Tanggal yang sempat melewati `toISOString()`.
    assert _tanggal_saring("2026-09-01T00:00:00.000Z") == "2026-09-01"
    assert _tanggal_saring("  2026-09-01  ") == "2026-09-01"
    # Bukan tanggal -> None, bukan dilempar.
    for buruk in ("", None, "kemarin", "2026-13-40", "01-09-2026", "2026/09/01"):
        assert _tanggal_saring(buruk) is None, buruk


# --------------------------------------------------------------------- #
# kolom baru yang dapat diurutkan
# --------------------------------------------------------------------- #
def test_spk_dan_periode_boleh_menjadi_dasar_pengurutan():
    assert Repo.URUTAN_BOLEH["spk"] == "po.name"
    assert "c.periodStart" in Repo.URUTAN_BOLEH["periode"]


def test_urutan_spk_memakai_kolom_purchase_order():
    urutan = Repo._urutan("spk", "asc")
    assert urutan.startswith("po.name ASC")
    # `c.id` tetap menjadi pemutus terakhir — tanpa itu dua baris bernomor
    # SPK sama dapat bertukar tempat antar halaman.
    assert urutan.endswith("c.id DESC")


def test_urutan_periode_memutus_dengan_akhir_periodenya():
    urutan = Repo._urutan("periode", "desc")
    assert "c.periodStart DESC" in urutan
    assert "c.periodEnd DESC" in urutan
    assert urutan.endswith("c.id DESC")


@pytest.mark.asyncio
async def test_pengurutan_spk_benar_benar_sampai_ke_sql(fake_db):
    db = fake_db(MODUL)
    await _panggil(db, sort_by="spk", sort_dir="asc")
    sql = _sql(db, "fetch_all")[0]
    assert "ORDER BY po.name ASC" in sql, sql
