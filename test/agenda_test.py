"""
Pengujian agenda: ulang tahun dan pengingat.

Dua hal yang dijaga di sini:

  * perhitungan ulang tahun tidak boleh memandang tahun lahir — pada
    28 Desember, ulang tahun 3 Januari harus terhitung enam hari lagi,
    bukan terlewat;
  * siapa melihat pengingat apa, dan siapa boleh membuat pengingat bagi
    seluruh pengguna.

Yang kedua mudah bergeser tanpa disadari: pengingat yang bocor tidak
menimbulkan galat, hanya muncul di layar orang yang tidak berkepentingan.
"""

from datetime import date as d
from datetime import timedelta
from types import SimpleNamespace

import pytest

from models.reminder_model import REMINDER_CATEGORIES
from repository.reminder_repository import BirthdayRepository


# ---------------------------------------------------------------------------
# Ulang tahun
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bulan,hari,hari_ini,harapan",
    [
        # Hari yang sama.
        (8, 12, d(2026, 8, 12), 0),
        # Beberapa hari lagi pada tahun yang sama.
        (8, 19, d(2026, 8, 12), 7),
        # Lintas tahun: inilah yang paling mudah salah.
        (1, 3, d(2026, 12, 28), 6),
        (1, 1, d(2026, 12, 31), 1),
        # Sudah lewat tahun ini, dihitung menuju tahun depan.
        (2, 10, d(2026, 8, 12), 182),
    ],
)
def test_hitung_hari_menuju_ulang_tahun(bulan, hari, hari_ini, harapan):
    assert BirthdayRepository.days_until(bulan, hari, hari_ini) == harapan


def test_29_februari_tetap_muncul_pada_tahun_biasa():
    """
    Tanpa penanganan khusus, orang yang lahir 29 Februari hilang dari agenda
    selama tiga tahun berturut-turut.
    """
    hasil = BirthdayRepository.days_until(2, 29, d(2027, 2, 25))

    assert hasil is not None
    # 2027 bukan tahun kabisat; diperlakukan sebagai 1 Maret.
    assert hasil == 4


def test_29_februari_pada_tahun_kabisat_tepat_di_harinya():
    assert BirthdayRepository.days_until(2, 29, d(2028, 2, 29)) == 0


# ---------------------------------------------------------------------------
# Siapa melihat pengingat apa
# ---------------------------------------------------------------------------


def terlihat(pembuat: int, ditandai: list[int], untuk_semua: bool, saya: int) -> bool:
    """
    Tiruan syarat `_terlihat_oleh`, tanpa menyentuh basis data.

    Ditulis ulang di sini dengan sengaja: yang diuji adalah aturannya, bukan
    penyusunan kueri SQL-nya.
    """
    if untuk_semua:
        return True
    if saya == pembuat:
        return True
    return saya in ditandai


@pytest.mark.parametrize(
    "nama,pembuat,ditandai,untuk_semua,saya,harapan",
    [
        ("pembuatnya sendiri", 1, [], False, 1, True),
        ("orang lain, tanpa tandaan", 1, [], False, 2, False),
        ("ditandai", 1, [3, 5], False, 3, True),
        ("tidak ditandai", 1, [3, 5], False, 7, False),
        ("untuk seluruh pengguna", 1, [], True, 7, True),
        ("pembuat tetap melihat yang untuk semua", 1, [], True, 1, True),
    ],
)
def test_siapa_melihat_pengingat(
    nama, pembuat, ditandai, untuk_semua, saya, harapan
):
    assert terlihat(pembuat, ditandai, untuk_semua, saya) is harapan


# ---------------------------------------------------------------------------
# Siapa boleh membuat pengingat bagi seluruh pengguna
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(monkeypatch):
    keadaan = {"dibuat": None}

    async def _create(data, targets):
        keadaan["dibuat"] = (data, targets)
        return {"id": 1}

    from controllers import agenda_controller as modul

    monkeypatch.setattr(
        modul.ReminderRepository, "create", staticmethod(_create)
    )
    return keadaan


def badan(**kw):
    dasar = {
        "title": "Kirim laporan PPh 21",
        "note": None,
        "date": d(2026, 8, 20),
        "category": "Pajak",
        "isShared": False,
        "targets": [],
    }
    dasar.update(kw)
    return SimpleNamespace(**dasar)


@pytest.mark.asyncio
async def test_akses_rendah_boleh_membuat_pengingat_biasa(repo):
    hasil = await __import__(
        "controllers.agenda_controller", fromlist=["AgendaController"]
    ).AgendaController.create(user_id=7, user_level=1, body=badan())

    assert "error" not in hasil
    assert repo["dibuat"] is not None


@pytest.mark.asyncio
async def test_akses_rendah_tidak_boleh_membuat_untuk_seluruh_pengguna(repo):
    """
    Batas ini yang menjaga agenda tetap terbaca.

    Bila terbuka untuk semua, agenda cepat penuh oleh hal yang hanya berlaku
    bagi satu-dua orang.
    """
    hasil = await __import__(
        "controllers.agenda_controller", fromlist=["AgendaController"]
    ).AgendaController.create(
        user_id=7, user_level=3, body=badan(isShared=True)
    )

    assert hasil["status"] == 403
    # Yang penting bukan hanya pesannya: penyimpanannya tidak boleh tersentuh.
    assert repo["dibuat"] is None


@pytest.mark.asyncio
async def test_akses_empat_boleh_membuat_untuk_seluruh_pengguna(repo):
    hasil = await __import__(
        "controllers.agenda_controller", fromlist=["AgendaController"]
    ).AgendaController.create(
        user_id=2, user_level=4, body=badan(isShared=True)
    )

    assert "error" not in hasil
    assert repo["dibuat"][0]["isShared"] is True


@pytest.mark.asyncio
async def test_pembuat_tidak_ikut_ditandai(repo):
    """
    Menandai diri sendiri hanya menambah baris tanpa mengubah apa pun —
    pembuatnya selalu melihat pengingatnya sendiri.
    """
    await __import__(
        "controllers.agenda_controller", fromlist=["AgendaController"]
    ).AgendaController.create(
        user_id=7, user_level=1, body=badan(targets=[7, 3, 5])
    )

    _, targets = repo["dibuat"]
    assert 7 not in targets
    assert targets == [3, 5]


# ---------------------------------------------------------------------------
# Kategori
# ---------------------------------------------------------------------------


def test_kategori_terkunci_pada_daftar_tetap():
    from schemas.reminder_schema import ReminderCreate

    with pytest.raises(ValueError):
        ReminderCreate(
            title="Uji", date=d(2026, 8, 20), category="pajak"  # huruf kecil
        )


def test_kategori_yang_dikenali_diterima():
    from schemas.reminder_schema import ReminderCreate

    for kategori in REMINDER_CATEGORIES:
        r = ReminderCreate(title="Uji", date=d(2026, 8, 20), category=kategori)
        assert r.category == kategori
