"""
Riwayat perubahan profil karyawan.

Profil hanya punya SATU baris per karyawan, dan tiap penyimpanan menimpanya.
Yang dijaga di sini: keadaan SEBELUM perubahan benar-benar tersalin, dan
tersalin SEBELUM baris profilnya ditimpa.

Urutan itu bukan kerapian. Terbalik, yang terekam adalah nilai barunya —
riwayatnya penuh, tetapi tidak memuat satu pun keadaan yang hilang, dan itu
baru ketahuan pada saat riwayatnya justru diperlukan.

Memakai basis data tiruan; tidak ada MySQL yang perlu berjalan.
"""

import asyncio
import json

from repository.employee_profile_repository import EmployeeProfileRepository

MODUL = "repository.employee_profile_repository"

#: Keadaan profil sebelum diubah.
PROFIL_LAMA = {
    "id": 7,
    "employeeID": 3,
    "birthPlace": "Bandnug",
    "motherName": "Siti",
    "bloodType": "O",
}


def _pasang(fake_db):
    """
    Antre jawaban basis data mengikuti urutan yang dipanggil `upsert`:

        1. fetch_one -> karyawan ada
        2. fetch_one -> profil lama ada (hanya id)
        3. fetch_one -> keadaan sebelum diubah, untuk disalin ke riwayat
    """
    db = fake_db(MODUL)
    db.queue("fetch_one", {"id": 3}, {"id": 7}, PROFIL_LAMA)
    return db


def _sql(query) -> str:
    return str(query)


def test_keadaan_lama_disalin_ke_riwayat(fake_db):
    db = _pasang(fake_db)

    hasil = asyncio.run(
        EmployeeProfileRepository.upsert(3, {"birthPlace": "Bandung"}, 9)
    )
    assert "error" not in hasil

    perintah = [_sql(q) for m, q in db.calls if m == "execute"]
    sisip = [q for q in perintah if "INSERT INTO employee_profile_history" in q]
    assert sisip, perintah


def test_riwayat_ditulis_sebelum_profil_ditimpa(fake_db):
    """
    Inti pengujian ini.

    Sesudah `UPDATE` berjalan, yang terbaca dari profil sudah nilai barunya —
    sehingga menyalin belakangan menghasilkan riwayat yang isinya sama persis
    dengan keadaan sekarang, dan tidak menyelamatkan apa pun.
    """
    db = _pasang(fake_db)
    asyncio.run(EmployeeProfileRepository.upsert(3, {"birthPlace": "Bandung"}, 9))

    perintah = [_sql(q) for m, q in db.calls if m == "execute"]
    urutan_sisip = next(
        i for i, q in enumerate(perintah)
        if "INSERT INTO employee_profile_history" in q
    )
    urutan_timpa = next(
        i for i, q in enumerate(perintah) if q.startswith("UPDATE employee_profiles")
    )
    assert urutan_sisip < urutan_timpa, perintah


def test_profil_baru_tidak_meninggalkan_riwayat(fake_db):
    """
    Pengisian PERTAMA tidak punya keadaan sebelumnya. Baris riwayat kosong di
    situ hanya menambah satu entri yang tidak dapat dibandingkan dengan apa
    pun.
    """
    db = fake_db(MODUL)
    db.queue("fetch_one", {"id": 3}, None)

    asyncio.run(EmployeeProfileRepository.upsert(3, {"birthPlace": "Bandung"}, 9))

    perintah = [_sql(q) for m, q in db.calls if m == "execute"]
    assert not [
        q for q in perintah if "INSERT INTO employee_profile_history" in q
    ], perintah


def test_riwayat_dibaca_terbaru_dulu(fake_db):
    """Yang dicari hampir selalu perubahan terakhir, bukan yang pertama."""
    db = fake_db(MODUL)
    db.queue(
        "fetch_all",
        [
            {
                "id": 2,
                "employeeID": 3,
                "snapshot": json.dumps(PROFIL_LAMA),
                "changedFields": json.dumps(["birthPlace"]),
                "changedAt": None,
                "changedBy": 9,
                "changedByName": "Ade",
            }
        ],
    )

    hasil = asyncio.run(EmployeeProfileRepository.history(3))
    assert isinstance(hasil, list) and len(hasil) == 1

    # Kolom JSON diurai, bukan diteruskan sebagai teks: layar memeriksanya
    # dengan `Array.isArray()`, yang menolak string.
    assert hasil[0]["snapshot"]["birthPlace"] == "Bandnug"
    assert hasil[0]["changedFields"] == ["birthPlace"]
    assert hasil[0]["changedByName"] == "Ade"

    assert "ORDER BY" in _sql(db.last_query("fetch_all"))
    assert "DESC" in _sql(db.last_query("fetch_all"))
