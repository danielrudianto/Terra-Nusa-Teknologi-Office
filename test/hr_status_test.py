"""
Tangga status pelamar, penghapusan hasil, dan biodata.

TANGGANYA

    baru          belum pernah membuka tautannya        [otomatis]
    mengerjakan   sudah menekan Mulai, belum mengirim   [otomatis]
    selesai       sudah mengirim jawabannya             [otomatis]
    dinilai       SELURUH soalnya sudah punya nilai     [otomatis]
    diwawancara   sudah diwawancarai                    [manual]
    diterima      berhasil                              [manual]
    ditolak       batal                                 [manual]

`dinilai` OTOMATIS, dan itu keputusan yang dijaga di sini. Tombol "tandai
sudah dinilai" berbohong ke dua arah: yang selesai menilai lalu lupa
menekannya membuat daftar menyatakan belum dinilai padahal sudah, dan yang
menekannya lebih dulu membuat daftar menyatakan sudah padahal baru separuh.
Keduanya hanya ketahuan dengan membuka lembarnya satu per satu — yang
justru hendak dihindari daftar itu.
"""

import pytest

from repository.hr_recruitment_repository import (
    STATUS_MANUAL,
    HrRecruitmentRepository,
)

MODUL = "repository.hr_recruitment_repository"
AUDIT = "repository.audit_log_repository"
HR = 4


def _perintah(db):
    return [
        str(q)
        for m, q in db.calls
        if m == "execute" and not str(q).startswith("INSERT INTO audit_logs")
    ]


# ---------------------------------------------------------------------
# Status otomatis: `dinilai`.
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_naik_ke_dinilai_saat_soal_terakhir_bernilai(fake_db):
    db = fake_db(MODUL)
    db.queue("fetch_one", {"status": "selesai", "submittedAt": "2026-09-20"})
    db.queue("fetch_val", 3, 3)  # 3 soal, 3 bernilai

    await HrRecruitmentRepository._selaraskan_status_nilai(5, 1)

    perintah = _perintah(db)
    assert perintah, "status tidak pernah ditulis"
    assert "status" in perintah[0]


@pytest.mark.asyncio
async def test_belum_naik_bila_masih_ada_yang_belum_dinilai(fake_db):
    """
    Dua dari tiga bukan "sudah dinilai". Menaikkannya membuat daftar
    menyatakan selesai atas lembar yang separuh kosong.
    """
    db = fake_db(MODUL)
    db.queue("fetch_one", {"status": "selesai", "submittedAt": "2026-09-20"})
    db.queue("fetch_val", 3, 2)

    await HrRecruitmentRepository._selaraskan_status_nilai(5, 1)

    assert not _perintah(db)


@pytest.mark.asyncio
async def test_MUNDUR_lagi_saat_satu_nilai_dicabut(fake_db):
    """
    Kalau tidak mundur, lembar yang nilainya dicabut tetap tampil "dinilai"
    — dan tidak ada yang akan kembali memeriksanya.
    """
    db = fake_db(MODUL)
    db.queue("fetch_one", {"status": "dinilai", "submittedAt": "2026-09-20"})
    db.queue("fetch_val", 3, 2)

    await HrRecruitmentRepository._selaraskan_status_nilai(5, 1)

    assert _perintah(db), "status tidak mundur saat nilainya dicabut"


@pytest.mark.asyncio
async def test_yang_sudah_diwawancara_TIDAK_mundur(fake_db):
    """
    Seseorang yang sudah diwawancarai lalu nilainya diperbaiki satu angka
    tidak boleh mundur menjadi "baru dinilai" — keputusan manusia tidak
    ditimpa oleh penyelarasan otomatis.
    """
    db = fake_db(MODUL)
    db.queue("fetch_one", {"status": "diwawancara", "submittedAt": "2026-09-20"})

    await HrRecruitmentRepository._selaraskan_status_nilai(5, 1)

    assert not _perintah(db)
    # Tidak perlu menghitung apa pun setelah tahu statusnya manual.
    assert db.executed("fetch_val") == 0


@pytest.mark.asyncio
async def test_yang_belum_mengirim_tidak_pernah_jadi_dinilai(fake_db):
    """
    Lembar yang ditinggalkan di tengah boleh dinilai, tetapi menaikkannya ke
    `dinilai` akan menyembunyikan kenyataan bahwa pelamarnya tidak pernah
    menyelesaikan ujiannya.
    """
    db = fake_db(MODUL)
    db.queue("fetch_one", {"status": "mengerjakan", "submittedAt": None})

    await HrRecruitmentRepository._selaraskan_status_nilai(5, 1)

    assert not _perintah(db)


@pytest.mark.asyncio
async def test_submittedAt_kosong_ditolak_WALAU_statusnya_selesai(fake_db):
    """
    Ditambahkan setelah sabotase lolos.

    Pengujian di atas memakai status `mengerjakan`, yang juga tersaring
    penjaga status di bawahnya — jadi ia tetap hijau walaupun penjaga
    `submittedAt` dicopot. Yang benar-benar menguji penjaga itu adalah
    baris yang TIDAK KONSISTEN: status `selesai` tanpa `submittedAt`,
    persis bentuk yang dihasilkan kekeliruan di tempat lain.
    """
    db = fake_db(MODUL)
    db.queue("fetch_one", {"status": "selesai", "submittedAt": None})
    db.queue("fetch_val", 3, 3)

    await HrRecruitmentRepository._selaraskan_status_nilai(5, 1)

    assert not _perintah(db)
    assert db.executed("fetch_val") == 0, (
        "sempat menghitung nilai untuk lembar yang belum dikirim"
    )


@pytest.mark.asyncio
async def test_paket_tanpa_soal_tidak_dianggap_dinilai(fake_db):
    """
    Nol dari nol bukan "sudah dinilai seluruhnya" — itu paket yang soalnya
    belum dibuat, dan menandainya selesai menyembunyikan kekeliruan HR.
    """
    db = fake_db(MODUL)
    db.queue("fetch_one", {"status": "selesai", "submittedAt": "2026-09-20"})
    db.queue("fetch_val", 0, 0)

    await HrRecruitmentRepository._selaraskan_status_nilai(5, 1)

    assert not _perintah(db)


# ---------------------------------------------------------------------
# Status manual.
# ---------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("status", list(STATUS_MANUAL))
async def test_status_manual_diterima(fake_db, status):
    db = fake_db(MODUL)
    db.queue("fetch_one", {"id": 5, "submittedAt": "2026-09-20"})

    hasil = await HrRecruitmentRepository.ubah_status_pelamar(5, status, HR)

    assert hasil["status"] == status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status", ["baru", "mengerjakan", "selesai", "dinilai", "apa-saja"]
)
async def test_status_otomatis_TIDAK_boleh_disetel_manual(fake_db, status):
    """
    Membiarkannya disetel manual berarti daftar dapat menyatakan "sudah
    dinilai" atas lembar yang belum disentuh siapa pun.
    """
    db = fake_db(MODUL)

    hasil = await HrRecruitmentRepository.ubah_status_pelamar(5, status, HR)

    assert hasil["status"] == 400
    assert db.executed("execute") == 0


@pytest.mark.asyncio
async def test_pelamar_tidak_ada_dijawab_404(fake_db):
    db = fake_db(MODUL)
    db.queue("fetch_one", None)

    hasil = await HrRecruitmentRepository.ubah_status_pelamar(
        999, "diterima", HR
    )

    assert hasil["status"] == 404


# ---------------------------------------------------------------------
# Hapus hasil.
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hapus_hasil_mengembalikan_ke_awal(fake_db):
    db = fake_db(MODUL, AUDIT)
    db.queue("fetch_one", {"id": 5})
    db.queue("execute", 12)

    hasil = await HrRecruitmentRepository.hapus_hasil(5, HR)

    assert hasil["jawabanDihapus"] == 12
    gabung = " ".join(_perintah(db))
    assert "DELETE FROM hr_answers" in gabung
    assert "UPDATE hr_candidates" in gabung


@pytest.mark.asyncio
async def test_hapus_hasil_TIDAK_menghapus_pelamarnya(fake_db):
    """
    Tautannya harus tetap sama supaya dapat dipakai mengerjakan lagi —
    itulah gunanya. Menghapus pelamarnya menuntut mendaftarkan yang baru
    dan menyalin tautan baru setiap kali.
    """
    db = fake_db(MODUL, AUDIT)
    db.queue("fetch_one", {"id": 5})
    db.queue("execute", 3)

    await HrRecruitmentRepository.hapus_hasil(5, HR)

    gabung = " ".join(_perintah(db))
    assert "DELETE FROM hr_candidates" not in gabung
    assert "isDelete" not in gabung
    assert "token" not in gabung, "tokennya ikut disentuh — tautannya berubah"


@pytest.mark.asyncio
async def test_hapus_hasil_dicatat_jejak_audit(fake_db):
    """
    Satu-satunya tindakan di modul ini yang membuang pekerjaan orang lain
    tanpa dapat dikembalikan.
    """
    db = fake_db(MODUL, AUDIT)
    db.queue("fetch_one", {"id": 5})
    db.queue("execute", 7)

    await HrRecruitmentRepository.hapus_hasil(5, HR)

    audit = [q for m, q in db.calls if m == "execute" and "audit_logs" in str(q)]
    assert audit, "penghapusan hasil tidak tercatat di jejak audit"


# ---------------------------------------------------------------------
# Biodata.
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_biodata_tidak_dapat_mengubah_nama(fake_db):
    """
    Nama dimasukkan HR saat mendaftarkan dan dipakai mencocokkan lembar
    dengan orangnya. Membiarkan pelamar menggantinya memutus pencocokan itu.
    """
    db = fake_db(MODUL)
    db.queue("fetch_one", {"id": 5, "submittedAt": None})

    await HrRecruitmentRepository.simpan_biodata(
        "tok", {"name": "Nama Palsu", "city": "Bekasi"}
    )

    perintah = " ".join(_perintah(db))
    assert "city" in perintah
    assert "name" not in perintah


@pytest.mark.asyncio
async def test_biodata_ditolak_setelah_dikirim(fake_db):
    db = fake_db(MODUL)
    db.queue("fetch_one", {"id": 5, "submittedAt": "2026-09-20"})

    hasil = await HrRecruitmentRepository.simpan_biodata("tok", {"city": "X"})

    assert hasil["status"] == 409
    assert not _perintah(db)


@pytest.mark.asyncio
async def test_biodata_token_tidak_berlaku_menjawab_none(fake_db):
    """
    `None`, bukan galat: rutenya yang mengubahnya menjadi 404 sekaligus
    mencatat percobaan gagal untuk pembatas laju.
    """
    db = fake_db(MODUL)
    db.queue("fetch_one", None)

    assert await HrRecruitmentRepository.simpan_biodata("x", {"city": "Y"}) is None
