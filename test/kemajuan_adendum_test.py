"""
Kemajuan proyek disusun ulang ketika NILAI KONTRAK berubah.

Kemajuan disimpan sebagai PERSEN. Yang tidak berubah saat adendum terbit
adalah pekerjaan yang sudah dikerjakan — persen adalah pekerjaan itu dibagi
nilai kontrak. Begitu penyebutnya berganti, seluruh angka lama menyatakan
hal yang berbeda dari yang dimaksud ketika dicatat.

Kasus yang disebut Daniel, dan yang menjadi uji pertama di bawah:

    kontrak 100, kemajuan 5%   -> pekerjaan senilai 5
    adendum memangkas jadi 50  -> pekerjaan yang sama = 10%

Bukan 2,5%. Yang dikalikan PERBANDINGAN TERBALIKNYA (lama / baru), karena
yang tetap adalah pembilangnya. Arah yang keliru menghasilkan angka yang
sama-sama masuk akal dilihat sekilas — itulah sebabnya diuji dengan angka,
bukan dibaca ulang.
"""

from decimal import Decimal

import pytest

import repository.project_progress_repository as modul
from repository.project_progress_repository import ProjectProgressRepository


class BasisTiruan:
    """Cukup untuk `fetch_all` baris kemajuan dan `execute` pembaruannya."""

    def __init__(self, baris):
        self.baris = [dict(b) for b in baris]
        self.tulisan = []

    async def fetch_all(self, _query):
        return [dict(b) for b in self.baris]

    async def execute(self, query):
        # Nilai yang ditulis dibaca dari kompilasi kuerinya; yang diuji
        # angkanya, bukan bentuk SQL-nya.
        nilai = dict(query.compile().params)
        self.tulisan.append(nilai)
        return 1


class AuditTiruan:
    def __init__(self):
        self.baris = []

    async def record(self, **kw):
        self.baris.append(kw)

    @staticmethod
    def diff(a, b):
        return {}


@pytest.fixture
def pasang(monkeypatch):
    def _pasang(baris):
        db = BasisTiruan(baris)
        audit = AuditTiruan()
        monkeypatch.setattr(modul, "database", db)

        import repository.audit_log_repository as mod_audit

        monkeypatch.setattr(mod_audit, "AuditLogRepository", audit)
        return db, audit

    return _pasang


def persen_tertulis(db):
    return [str(t["percentage"]) for t in db.tulisan]


# --------------------------------------------------------------- aritmatika


@pytest.mark.asyncio
async def test_kontrak_dipangkas_separuh_menaikkan_persennya(pasang):
    db, audit = pasang([{"id": 1, "percentage": Decimal("5.00")}])

    hasil = await ProjectProgressRepository.skalakan(
        7, 100, 50, userID=3, sebab="adendum ADD-001"
    )

    assert hasil == {"disesuaikan": 1}
    assert persen_tertulis(db) == ["10.00"]


@pytest.mark.asyncio
async def test_kontrak_membesar_menurunkan_persennya(pasang):
    # Aturan yang sama, arah sebaliknya: pekerjaan yang sama menjadi bagian
    # yang lebih kecil dari lingkup yang lebih besar.
    db, _ = pasang([{"id": 1, "percentage": Decimal("10.00")}])

    await ProjectProgressRepository.skalakan(7, 50, 100, userID=3, sebab="adendum")

    assert persen_tertulis(db) == ["5.00"]


@pytest.mark.asyncio
async def test_seluruh_riwayat_ikut_disesuaikan(pasang):
    # Kurva S dibaca sebagai satu garis; menyesuaikan sebagian membuat
    # garisnya patah tepat di tanggal adendumnya.
    db, _ = pasang(
        [
            {"id": 1, "percentage": Decimal("5.00")},
            {"id": 2, "percentage": Decimal("12.50")},
            {"id": 3, "percentage": Decimal("30.00")},
        ]
    )

    await ProjectProgressRepository.skalakan(7, 100, 50, userID=3, sebab="adendum")

    assert persen_tertulis(db) == ["10.00", "25.00", "60.00"]


@pytest.mark.asyncio
async def test_hasil_boleh_melewati_seratus(pasang):
    """
    Lingkup dipangkas di bawah pekerjaan yang sudah jadi.

    Dibatasi seratus, keadaan ini terbaca persis seperti proyek yang selesai
    tepat waktu — padahal kontraknya tidak lagi menutup pekerjaan yang sudah
    terlanjur dikerjakan.
    """
    db, _ = pasang([{"id": 1, "percentage": Decimal("60.00")}])

    await ProjectProgressRepository.skalakan(7, 100, 50, userID=3, sebab="adendum")

    assert persen_tertulis(db) == ["120.00"]


@pytest.mark.asyncio
async def test_pembulatan_dua_angka(pasang):
    db, _ = pasang([{"id": 1, "percentage": Decimal("33.33")}])

    await ProjectProgressRepository.skalakan(7, 100, 30, userID=3, sebab="adendum")

    # 33.33 * 100 / 30 = 111.1
    assert persen_tertulis(db) == ["111.10"]


# ------------------------------------------------------------- keadaan batas


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lama,baru",
    [
        (100, 0),    # kontrak dipangkas habis — pembagian terhadap nol
        (0, 100),    # dahulu belum ada kontrak — tidak ada perbandingannya
        (0, 0),
        (100, 100),  # nilainya tidak berubah
    ],
)
async def test_tidak_menyentuh_apa_pun(pasang, lama, baru):
    # Angka lama yang salah lebih baik daripada angka baru yang dikarang.
    db, audit = pasang([{"id": 1, "percentage": Decimal("5.00")}])

    hasil = await ProjectProgressRepository.skalakan(
        7, lama, baru, userID=3, sebab="adendum"
    )

    assert hasil == {"disesuaikan": 0}
    assert db.tulisan == []
    assert audit.baris == []


@pytest.mark.asyncio
async def test_proyek_tanpa_catatan_kemajuan(pasang):
    db, _ = pasang([])
    hasil = await ProjectProgressRepository.skalakan(7, 100, 50, 3, "adendum")
    assert hasil == {"disesuaikan": 0}
    assert db.tulisan == []


@pytest.mark.asyncio
async def test_baris_yang_tidak_bergeser_tidak_ditulis_ulang(pasang):
    # Nol tetap nol berapa pun kontraknya; menulis ulang hanya menambah
    # baris jejak yang tidak menyatakan perubahan apa pun.
    db, audit = pasang([{"id": 1, "percentage": Decimal("0.00")}])

    hasil = await ProjectProgressRepository.skalakan(7, 100, 50, 3, "adendum")

    assert hasil == {"disesuaikan": 0}
    assert db.tulisan == []
    assert audit.baris == []


# ------------------------------------------------------------------- jejak


@pytest.mark.asyncio
async def test_jejaknya_menyebut_sistem_dan_sebabnya(pasang):
    db, audit = pasang([{"id": 1, "percentage": Decimal("5.00")}])

    await ProjectProgressRepository.skalakan(
        7, 100, 50, userID=3, sebab="adendum ADD-001"
    )

    assert len(audit.baris) == 1
    j = audit.baris[0]
    # Aksi TERSENDIRI: baris ini tidak boleh terbaca seperti seseorang
    # mengetik ulang angkanya.
    assert j["action"] == "progress_rebase"
    assert j["entity"] == "project_progress"
    assert j["entityID"] == 1
    # Orang yang menerbitkan adendumnya TETAP tercatat: sistem
    # menindaklanjuti perbuatan seseorang, bukan bertindak sendiri.
    assert j["userID"] == 3
    assert "ADD-001" in j["note"]
    assert "sistem" in j["note"].lower()
    assert j["changes"]["percentage"] == {"from": "5.00", "to": "10.00"}
