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
    # Kolom JSON kembali sebagai TEKS dari `databases`; bentuk itulah yang
    # harus ditangani, bukan bentuk yang sudah terurai.
    "formalEducation": '[{"jenjang": "S1"}]',
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


def test_snapshot_diserahkan_sebagai_objek_bukan_teks(fake_db):
    """
    Kolom `snapshot` bertipe JSON, dan tipe itu menyandikan nilainya SENDIRI
    saat mengikat. Menyandikannya lebih dulu di sini membuatnya tersandi dua
    kali: yang tersimpan bukan objek melainkan teks yang kebetulan berisi
    objek.

    Dari aplikasi hal itu tidak terlihat — pembacanya mengurai sekali, dan
    satu penguraian atas nilai tersandi ganda kebetulan menghasilkan bentuk
    yang benar. Yang patah SQL-nya: `JSON_EXTRACT` dan `JSON_TABLE` atas
    riwayatnya berhenti menemukan apa pun, sebab bagi MySQL isinya satu teks.

    Persis itu yang sudah terjadi pada `employee_profiles.familyMembers`:
    `JSON_TYPE` melaporkan STRING, bukan ARRAY, dan kuerinya kembali kosong.
    """
    db = _pasang(fake_db)
    asyncio.run(EmployeeProfileRepository.upsert(3, {"birthPlace": "Bandung"}, 9))

    sisip = next(
        q for m, q in db.calls
        if m == "execute" and "employee_profile_history" in _sql(q)
    )
    nilai = sisip.compile().params

    # Objek, bukan teks — inilah yang membedakan sandi tunggal dari ganda.
    assert isinstance(nilai["snapshot"], dict), type(nilai["snapshot"])
    assert isinstance(nilai["changedFields"], list), type(nilai["changedFields"])

    # Kolom JSON di dalamnya tetap berupa daftar, bukan teks: layar
    # memeriksanya dengan `Array.isArray()`, yang menolak string.
    assert isinstance(nilai["snapshot"]["formalEducation"], list)


def test_snapshot_menerima_tanggal(fake_db):
    """
    `date` tidak dapat diserialkan JSON sendiri.

    Itu sebabnya `default=str` dulu dipakai — tetapi `json.dumps` menghasilkan
    teks, dan teks itulah yang menimbulkan sandi ganda. `_jsonkan` menangani
    keduanya: tanggalnya menjadi teks, wadahnya tetap objek.
    """
    from datetime import date

    db = fake_db(MODUL)
    db.queue("fetch_one", {"id": 3}, {"id": 7},
             {**PROFIL_LAMA, "ktpValidUntil": date(2030, 1, 31)})

    asyncio.run(EmployeeProfileRepository.upsert(3, {"birthPlace": "Bandung"}, 9))

    sisip = next(
        q for m, q in db.calls
        if m == "execute" and "employee_profile_history" in _sql(q)
    )
    nilai = sisip.compile().params
    assert nilai["snapshot"]["ktpValidUntil"] == "2030-01-31"


def test_hanya_kolom_yang_berubah_dicatat(fake_db):
    """
    Layar mengirim SELURUH isian setiap kali menyimpan. Mencatat apa yang
    dikirim berarti satu koreksi satu huruf tercatat sebagai dua puluh kolom
    berubah.
    """
    db = _pasang(fake_db)
    asyncio.run(
        EmployeeProfileRepository.upsert(
            3,
            # `motherName` dikirim ulang dengan nilai yang SAMA.
            {"birthPlace": "Bandung", "motherName": "Siti"},
            9,
        )
    )

    sisip = next(
        q for m, q in db.calls
        if m == "execute" and "employee_profile_history" in _sql(q)
    )
    berubah = sisip.compile().params["changedFields"]
    assert berubah == ["birthPlace"], berubah


def test_kolom_berulang_yang_tidak_disunting_tidak_tercatat(fake_db):
    """
    Kolom JSON dibandingkan dalam bentuk TERURAI, bukan sebagai teks.

    Keadaan lamanya sudah diurai `_rapikan` menjadi list; muatan barunya masih
    teks JSON karena rutenya menyandikannya lebih dulu agar dapat disimpan
    MySQL. List dan teks tidak pernah sama, sehingga kelima kolom berulang —
    pendidikan, pengalaman, bahasa, susunan keluarga, SIM — tercatat berubah
    pada SETIAP penyimpanan, termasuk ketika yang disunting hanya satu kata di
    kolom lain.

    Riwayat yang menyebut lima hal berubah padahal satu, sama tidak dapat
    dipercayanya dengan riwayat yang tidak menyebut apa pun.
    """
    db = _pasang(fake_db)
    asyncio.run(
        EmployeeProfileRepository.upsert(
            3,
            {
                "birthPlace": "Bandung",
                # Isi yang SAMA dengan `PROFIL_LAMA`, dalam bentuk yang
                # benar-benar dikirim rutenya: teks JSON.
                "formalEducation": '[{"jenjang": "S1"}]',
            },
            9,
        )
    )

    sisip = next(
        q for m, q in db.calls
        if m == "execute" and "employee_profile_history" in _sql(q)
    )
    berubah = sisip.compile().params["changedFields"]
    assert berubah == ["birthPlace"], berubah


def test_kolom_berulang_yang_disunting_tetap_tercatat(fake_db):
    """Kebalikannya: perubahan sungguhan pada kolom berulang harus terbaca."""
    db = _pasang(fake_db)
    asyncio.run(
        EmployeeProfileRepository.upsert(
            3, {"formalEducation": '[{"jenjang": "S2"}]'}, 9
        )
    )

    sisip = next(
        q for m, q in db.calls
        if m == "execute" and "employee_profile_history" in _sql(q)
    )
    berubah = sisip.compile().params["changedFields"]
    assert berubah == ["formalEducation"], berubah


def test_pengosongan_benar_benar_tersimpan(fake_db):
    """
    Nilai `None` bukan "tidak dikirim", melainkan "sengaja dikosongkan".

    Rutenya memakai `model_dump(exclude_unset=True)`, jadi kolom yang tidak
    dikirim tidak pernah sampai ke repositori. Menyaring `None` di sini
    membuat pengosongan tidak pernah tersimpan: nilai lama bertahan, riwayat
    tidak mencatat apa-apa, dan layar tetap menyatakan berhasil.

    Justru di profil karyawan itu yang paling merugikan — nomor BPJS atau
    tempat lahir yang keliru tidak dapat dihapus, hanya dapat ditimpa nilai
    lain yang juga keliru.
    """
    db = _pasang(fake_db)
    asyncio.run(EmployeeProfileRepository.upsert(3, {"birthPlace": None}, 9))

    timpa = next(
        q for m, q in db.calls
        if m == "execute" and _sql(q).startswith("UPDATE employee_profiles")
    )
    nilai = timpa.compile().params
    assert "birthPlace" in nilai, nilai
    assert nilai["birthPlace"] is None, nilai

    sisip = next(
        q for m, q in db.calls
        if m == "execute" and "employee_profile_history" in _sql(q)
    )
    berubah = sisip.compile().params["changedFields"]
    assert berubah == ["birthPlace"], berubah
