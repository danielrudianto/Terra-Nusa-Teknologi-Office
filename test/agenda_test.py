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


# ---------------------------------------------------------------------------
# Ulang tahun pasangan
# ---------------------------------------------------------------------------
#
# Diambil dari `familyMembers` pada profil karyawan — kolom JSON yang kembali
# sebagai TEKS, berisi larik `{relation, name, birthday, ...}`.
#
# Yang paling mudah salah di sini bukan penyaringannya, melainkan pembacaan
# tanggalnya: dua bentuk beredar di basis data, dan yang lama tergeser sehari.

import json

from repository.reminder_repository import _pasangan, _tanggal_keluarga

MODUL_PENGINGAT = "repository.reminder_repository"


def _jawaban(*anggota, kunci="family"):
    """
    Satu baris hasil join karyawan + jawaban formulir berkala TERAKHIR.

    Bentuknya diambil dari data sungguhan: `answers` adalah objek berkunci
    `key` tiap isian, dan daftar keluarganya berkunci `family` dengan
    `relation` bernilai "Pasangan"/"Anak" — huruf besar, sesuai `options` pada
    definisi isiannya.
    """
    return {
        "id": 3,
        "name": "Budi",
        "answers": json.dumps({"shift": True, kunci: list(anggota),
                               "dependents": len(anggota)}),
    }


def _jawaban_ganda(*anggota):
    """
    Bentuk yang TERSANDI DUA KALI.

    Ada sungguhan di basis data ini: `employee_profiles.familyMembers`
    sebagian bertipe ARRAY dan sebagian STRING berisi teks JSON, karena
    pemanggilnya menyandikan sendiri lalu tipe kolom JSON menyandikannya
    sekali lagi. Pembacanya harus tahan terhadap keduanya.
    """
    return {
        "id": 3,
        "name": "Budi",
        "answers": json.dumps(json.dumps({"family": list(anggota)})),
    }


def test_tanggal_bentuk_baru_dibaca_apa_adanya():
    """`tanggalLokal()` di layar profil menyimpannya sebagai `YYYY-MM-DD`."""
    assert _tanggal_keluarga("1990-05-12") == d(1990, 5, 12)


def test_tanggal_bentuk_lama_dikembalikan_ke_waktu_jakarta():
    """
    Inti pengujian ini.

    Sebelum `tanggalLokal()` dipakai, objek Date dari datepicker langsung
    diserialkan — dan `toISOString()` mengubahnya ke UTC lebih dulu. Tengah
    malam tanggal 12 di Jakarta adalah pukul 17.00 tanggal 11 menurut UTC.

    Membaca bagian tanggalnya begitu saja MEMUNDURKAN ulang tahunnya sehari,
    tanpa galat apa pun: yang terjadi hanya ucapan selamat yang datang sehari
    lebih cepat, setiap tahun, dan tidak ada yang menghubungkannya dengan
    kode.

    Paling merugikan pada pergantian bulan: 1 Januari terbaca 31 Desember.
    """
    assert _tanggal_keluarga("2026-05-11T17:00:00.000Z") == d(2026, 5, 12)
    assert _tanggal_keluarga("2025-12-31T17:00:00.000Z") == d(2026, 1, 1)


def test_tanggal_yang_tidak_terbaca_dilewati():
    for nilai in ("", None, "kemarin", "12/05/1990", "0000-00-00"):
        assert _tanggal_keluarga(nilai) is None


def test_hanya_pasangan_yang_diambil():
    """
    Anak dan saudara sengaja tidak ikut.

    Satu karyawan dapat menyumbang empat tanggal sekaligus, dan agenda yang
    terlalu ramai berhenti dibaca — persis yang hendak dihindari dengan
    menampilkannya.
    """
    baris = _jawaban(
        # Huruf besar, seperti yang benar-benar tersimpan.
        {"relation": "Pasangan", "name": "Siti", "birthday": "1992-03-04"},
        {"relation": "Anak", "name": "Rani", "birthday": "2018-07-09"},
        {"relation": "saudara", "name": "Joko", "birthday": "1988-01-02"},
    )
    hasil = _pasangan(baris["answers"])
    assert [x["nama"] for x in hasil] == ["Siti"]


def test_pasangan_tanpa_nama_atau_tanggal_dilewati():
    """Tanggal tanpa nama tidak dapat diucapkan kepada siapa pun."""
    baris = _jawaban(
        {"relation": "Pasangan", "name": "", "birthday": "1992-03-04"},
        {"relation": "Pasangan", "name": "Siti", "birthday": ""},
        {"relation": "Pasangan", "name": "Ani", "birthday": "1993-06-07"},
    )
    assert [x["nama"] for x in _pasangan(baris["answers"])] == ["Ani"]


def test_familyMembers_rusak_tidak_melempar_galat():
    """
    Satu profil yang isinya tidak dapat diurai tidak boleh mengosongkan
    seluruh agenda; ia cukup dilewati.
    """
    assert _pasangan("{bukan json") == []
    assert _pasangan(None) == []
    assert _pasangan('"teks biasa"') == []
    assert _pasangan(json.dumps({"family": "bukan larik"})) == []
    assert _pasangan(json.dumps({"family": ["bukan objek"]})) == []
    # Formulir yang belum punya isian keluarga sama sekali.
    assert _pasangan(json.dumps({"shift": True})) == []


def test_agenda_memuat_karyawan_dan_pasangan(fake_db):
    """
    Keduanya dalam satu daftar, dibedakan `kind`.

    Tanpa penanda itu layar tidak dapat membedakan "Budi ulang tahun" dari
    "istri Budi ulang tahun", dan keduanya menuntut kalimat yang berbeda.
    """
    import asyncio

    db = fake_db(MODUL_PENGINGAT)
    hari_ini = d(2026, 5, 10)
    db.queue(
        "fetch_all",
        # Ulang tahun karyawan.
        [{"id": 3, "name": "Budi", "birthday": d(1990, 5, 12)}],
        # Profil beserta keluarganya.
        [_jawaban({"relation": "Pasangan", "name": "Siti",
                  "birthday": "1992-05-11"})],
    )

    hasil = asyncio.run(BirthdayRepository.upcoming(hari_ini, 7))

    jenis = {x["name"]: x["kind"] for x in hasil}
    assert jenis == {"Budi": "employee", "Siti": "spouse"}

    siti = next(x for x in hasil if x["name"] == "Siti")
    # Id KARYAWANNYA: pasangan tidak punya baris sendiri, dan yang dituju saat
    # barisnya ditekan memang karyawannya.
    assert siti["id"] == 3
    assert siti["employeeName"] == "Budi"
    assert siti["daysUntil"] == 1


def test_pasangan_di_luar_jangkauan_tidak_ikut(fake_db):
    import asyncio

    db = fake_db(MODUL_PENGINGAT)
    db.queue(
        "fetch_all",
        [],
        [_jawaban({"relation": "Pasangan", "name": "Siti",
                  "birthday": "1992-11-20"})],
    )

    hasil = asyncio.run(BirthdayRepository.upcoming(d(2026, 5, 10), 7))
    assert hasil == []


def test_profil_gagal_dibaca_tidak_menjatuhkan_ulang_tahun_karyawan(fake_db):
    """
    Kegagalan sumber kedua tidak boleh menghapus sumber pertama yang sudah
    terkumpul — pengguna melihat "agenda kosong" tanpa tahu bagian mana yang
    gagal.
    """
    import asyncio

    db = fake_db(MODUL_PENGINGAT)
    db.queue(
        "fetch_all",
        [{"id": 3, "name": "Budi", "birthday": d(1990, 5, 12)}],
    )
    # Antrean kedua sengaja dikosongkan; pemanggilan berikutnya melempar.

    hasil = asyncio.run(BirthdayRepository.upcoming(d(2026, 5, 10), 7))
    assert [x["name"] for x in hasil] == ["Budi"]


def test_kalender_rentang_memuat_pasangan(fake_db):
    """Halaman kalender memakai jalur lain; keduanya harus sepakat."""
    import asyncio

    db = fake_db(MODUL_PENGINGAT)
    db.queue(
        "fetch_all",
        [],
        [_jawaban({"relation": "Pasangan", "name": "Siti",
                  "birthday": "1992-05-11"})],
    )

    hasil = asyncio.run(
        BirthdayRepository.in_range(d(2026, 5, 1), d(2026, 5, 31))
    )
    assert len(hasil) == 1
    assert hasil[0]["name"] == "Siti"
    assert hasil[0]["date"] == d(2026, 5, 11)
    assert hasil[0]["kind"] == "spouse"
    # Tahun lahir pasangan tidak diumumkan: untuk mengucapkan selamat,
    # tanggal dan bulan sudah cukup.
    assert "age" not in hasil[0]
    assert "birthday" not in hasil[0]


def test_ejaan_pasangan_tidak_peka_huruf_besar():
    """
    Dua ejaan beredar dan keduanya harus terbaca.

    Formulir berkala menyimpan "Pasangan" — huruf besar, dari `options` pada
    definisi isiannya. Layar profil memakai "pasangan". Mencocokkan persis
    membuat SELURUH data yang ada tidak terbaca, dan agendanya kosong tanpa
    satu pun galat.
    """
    for ejaan in ("Pasangan", "pasangan", "PASANGAN", " Pasangan "):
        baris = _jawaban({"relation": ejaan, "name": "Siti",
                          "birthday": "1992-03-04"})
        assert [x["nama"] for x in _pasangan(baris["answers"])] == ["Siti"], ejaan


def test_jawaban_tersandi_ganda_tetap_terbaca():
    """
    Sandi ganda benar-benar ada di basis data ini.

    Pemanggilnya menyandikan sendiri dengan `json.dumps`, lalu tipe kolom JSON
    pada SQLAlchemy menyandikannya SEKALI LAGI saat mengikat nilainya. Yang
    sampai ke MySQL bukan objek, melainkan teks yang kebetulan berisi objek —
    dan pembacanya melihat `str`, bukan `dict`.
    """
    baris = _jawaban_ganda({"relation": "Pasangan", "name": "Siti",
                            "birthday": "1992-03-04"})
    assert [x["nama"] for x in _pasangan(baris["answers"])] == ["Siti"]


def test_hanya_pengisian_terakhir_yang_dibaca(fake_db):
    """
    Satu karyawan mengisi berulang kali tiap periode.

    Membaca semuanya memunculkan pasangan yang sudah bercerai atau nama yang
    sudah dibetulkan — dua kali, berdampingan, tanpa penjelasan apa pun bagi
    yang membacanya. Yang dijaga di sini kuerinya memang MENGELOMPOKKAN per
    karyawan dan mengambil id terbesar.
    """
    import asyncio

    db = fake_db(MODUL_PENGINGAT)
    db.queue("fetch_all", [], [])
    asyncio.run(BirthdayRepository.upcoming(d(2026, 5, 10), 7))

    kueri = str(db.calls[-1][1])
    assert "GROUP BY" in kueri
    assert "max(" in kueri.lower()
