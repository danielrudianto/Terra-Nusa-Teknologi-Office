"""
Agenda mencatat jejak audit — sebelumnya TIDAK SAMA SEKALI.

KENAPA AGENDA PERLU JEJAK

Pengingat bukan catatan pribadi. `isShared` membuatnya tampil di agenda
SELURUH pengguna, dan tandaan (`targets`) menyeret orang lain ke dalamnya.
Barisnya karena itu bukan milik pembuatnya saja: yang lain melihatnya, dan
yang lain juga dapat mengubah tanggalnya atau menghapusnya.

Tanpa jejak, "kok agendanya hilang" dan "kok tanggalnya pindah" tidak punya
jawaban sama sekali — bukan jawaban yang sulit dicari, melainkan tidak ada.

EMPAT HAL YANG DIJAGA DI SINI

1. Ketiga aksinya tercatat: buat, ubah, hapus.
2. Mengubah menyebut nilai LAMA. Yang ditanyakan orang pada agenda justru
   tanggalnya yang dulu, bukan yang sekarang — yang sekarang sudah di layar.
3. Menghapus menyertakan JUDULNYA. Sesudah `isDelete = 1`, "menghapus
   pengingat #41" tidak memberi tahu siapa pun apa yang hilang.
4. Penyimpanan yang tidak mengubah apa pun TIDAK dicatat. Daftar penuh baris
   "diubah" tanpa isi membuat yang sungguhan tenggelam.
"""

import pytest

from repository.reminder_repository import ReminderRepository

MODUL = "repository.reminder_repository"


@pytest.fixture
def jejak(monkeypatch):
    """Tangkap setiap panggilan `AuditLogRepository.record`."""
    from repository.audit_log_repository import AuditLogRepository

    tercatat: list[dict] = []

    async def _record(**kw):
        tercatat.append(kw)
        return True

    monkeypatch.setattr(AuditLogRepository, "record", staticmethod(_record))
    return tercatat


class TestBuat:
    @pytest.mark.asyncio
    async def test_tercatat_sebagai_create(self, fake_db, jejak):
        db = fake_db(MODUL)
        db.queue("execute", 41)

        hasil = await ReminderRepository.create(
            {"title": "Rapat vendor", "date": "2026-10-01", "category": "Rapat"},
            [],
        )

        assert hasil == {"id": 41}
        assert len(jejak) == 1
        assert jejak[0]["entity"] == "reminders"
        assert jejak[0]["entityID"] == 41
        assert jejak[0]["action"] == "create"

    @pytest.mark.asyncio
    async def test_isinya_ikut_tercatat(self, fake_db, jejak):
        db = fake_db(MODUL)
        db.queue("execute", 41)

        await ReminderRepository.create(
            {"title": "Rapat vendor", "date": "2026-10-01", "category": "Rapat"},
            [],
        )

        ubah = jejak[0]["changes"] or {}
        assert ubah["title"]["to"] == "Rapat vendor"
        assert ubah["category"]["to"] == "Rapat"

    @pytest.mark.asyncio
    async def test_tandaan_dicatat_sebagai_NAMA_bukan_id(self, fake_db, jejak):
        """
        "targets: 4, 9" tidak menjelaskan apa pun tanpa membuka tabel
        pengguna; yang dicari selalu "siapa yang ditandai".
        """
        db = fake_db(MODUL)
        db.queue("execute", 41)
        db.queue("fetch_all", [{"id": 4, "name": "Rina"}, {"id": 9, "name": "Budi"}])

        await ReminderRepository.create({"title": "Rapat"}, [4, 9])

        assert jejak[0]["changes"]["targets"]["to"] == "Rina, Budi"

    @pytest.mark.asyncio
    async def test_nama_tandaan_gagal_dibaca_tidak_menjatuhkan_apa_pun(
        self, fake_db, jejak
    ):
        db = fake_db(MODUL)
        db.queue("execute", 41)
        db.fail("fetch_all", RuntimeError("koneksi putus"))

        hasil = await ReminderRepository.create({"title": "Rapat"}, [4])

        # Pengingatnya tetap tersimpan; id-nya dipakai sebagai cadangan.
        assert hasil == {"id": 41}
        assert jejak[0]["changes"]["targets"]["to"] == "4"


class TestUbah:
    @pytest.mark.asyncio
    async def test_menyebut_nilai_lama_dan_baru(self, fake_db, jejak):
        db = fake_db(MODUL)
        db.queue(
            "fetch_one",
            {"id": 41, "title": "Rapat vendor", "date": "2026-10-01"},
        )

        await ReminderRepository.update(41, {"date": "2026-10-08"}, None)

        assert len(jejak) == 1
        assert jejak[0]["action"] == "update"
        ubah = jejak[0]["changes"]
        assert ubah["date"]["from"] == "2026-10-01"
        assert ubah["date"]["to"] == "2026-10-08"
        # Yang tidak berubah tidak ikut disebut.
        assert "title" not in ubah

    @pytest.mark.asyncio
    async def test_penyimpanan_tanpa_perubahan_tidak_dicatat(self, fake_db, jejak):
        db = fake_db(MODUL)
        db.queue("fetch_one", {"id": 41, "title": "Rapat vendor"})

        await ReminderRepository.update(41, {"title": "Rapat vendor"}, None)

        assert jejak == []

    @pytest.mark.asyncio
    async def test_tandaan_berubah_tercatat_sebagai_nama(self, fake_db, jejak):
        db = fake_db(MODUL)
        db.queue("fetch_one", {"id": 41, "title": "Rapat"})
        db.queue("fetch_all", [{"userID": 4}])                    # tandaan lama
        db.queue("fetch_all", [{"id": 4, "name": "Rina"}])        # nama lama
        db.queue(
            "fetch_all",
            [{"id": 4, "name": "Rina"}, {"id": 9, "name": "Budi"}],  # nama baru
        )

        await ReminderRepository.update(41, {}, [4, 9])

        ubah = jejak[0]["changes"]
        assert ubah["targets"]["from"] == "Rina"
        assert ubah["targets"]["to"] == "Rina, Budi"

    @pytest.mark.asyncio
    async def test_seluruh_tandaan_dilepas_terbaca_jelas(self, fake_db, jejak):
        db = fake_db(MODUL)
        db.queue("fetch_one", {"id": 41, "title": "Rapat"})
        db.queue("fetch_all", [{"userID": 4}])
        db.queue("fetch_all", [{"id": 4, "name": "Rina"}])
        db.queue("fetch_all", [])

        await ReminderRepository.update(41, {}, [])

        assert jejak[0]["changes"]["targets"]["to"] == "(tidak ada)"


class TestHapus:
    @pytest.mark.asyncio
    async def test_tercatat_sebagai_delete(self, fake_db, jejak):
        db = fake_db(MODUL)
        db.queue("fetch_one", {"id": 41, "title": "Rapat vendor"})

        await ReminderRepository.soft_delete(41)

        assert len(jejak) == 1
        assert jejak[0]["action"] == "delete"
        assert jejak[0]["entityID"] == 41

    @pytest.mark.asyncio
    async def test_judulnya_ikut_supaya_tahu_apa_yang_hilang(self, fake_db, jejak):
        db = fake_db(MODUL)
        db.queue("fetch_one", {"id": 41, "title": "Rapat vendor"})

        await ReminderRepository.soft_delete(41)

        assert jejak[0]["note"] == "Rapat vendor"

    @pytest.mark.asyncio
    async def test_baris_yang_tidak_ketemu_tetap_dicatat(self, fake_db, jejak):
        """
        Judulnya memang tidak ada, tetapi penghapusannya tetap terjadi —
        jejaknya tidak boleh ikut hilang bersama judulnya.
        """
        db = fake_db(MODUL)
        db.queue("fetch_one", None)

        await ReminderRepository.soft_delete(41)

        assert len(jejak) == 1
        assert jejak[0]["note"] is None


class TestPencatatanBukanPenghalang:
    @pytest.mark.asyncio
    async def test_gagal_mencatat_tidak_menggagalkan_penyimpanan(
        self, fake_db, monkeypatch
    ):
        """
        Kegagalan pencatatan tidak boleh membatalkan operasi utama — sama
        seperti janji `AuditLogRepository.record` sendiri. Di sini yang
        dilempar `record`-nya, bukan basis datanya.
        """
        from repository.audit_log_repository import AuditLogRepository

        async def _meledak(**_kw):
            raise RuntimeError("tabel audit penuh")

        monkeypatch.setattr(AuditLogRepository, "record", staticmethod(_meledak))

        db = fake_db(MODUL)
        db.queue("fetch_one", {"id": 41, "title": "Rapat"})

        hasil = await ReminderRepository.soft_delete(41)

        # Penghapusannya SUDAH dijalankan sebelum pencatatan; yang penting
        # di sini balikannya tidak menipu.
        assert "error" in hasil or "message" in hasil
