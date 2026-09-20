"""
Menilai jawaban ujian — bagian yang SEBELUMNYA TIDAK ADA SAMA SEKALI.

Kolom `score`, `checkedBy`, `checkedAt`, dan `checkerNote` sudah ada di
`hr_answers` sejak awal, lengkap dengan keterangan yang membedakan NULL dari
nol. Tidak satu pun pernah ditulis di mana pun dalam repo ini, dan tidak ada
endpoint yang mengembalikan jawaban pelamar.

Akibatnya baru terasa ketika ujian pertama benar-benar dikerjakan: jawabannya
tersimpan rapi, lalu tidak dapat dibaca kecuali lewat SQL langsung.

Yang dijaga di sini adalah keputusan-keputusan yang mudah tergerus:

  * NULL bukan nol — dan sebaliknya;
  * soal yang TIDAK DIJAWAB tetap muncul di lembar penilaian;
  * nilai tidak boleh melampaui `maxScore` soalnya, dan batas itu dibaca
    dari basis data, bukan dipercaya dari muatan;
  * soal milik paket lain tidak dapat dinilai.
"""

import pytest

from repository.hr_recruitment_repository import (
    HrRecruitmentRepository,
    kode_peserta,
)

MODUL = "repository.hr_recruitment_repository"
PEMERIKSA = 7


# ---------------------------------------------------------------------
# Kode peserta.
# ---------------------------------------------------------------------


def test_kode_peserta_tidak_membocorkan_token():
    """
    Token adalah KUNCI ujian: selama belum dikirim, siapa pun yang
    memegangnya dapat membuka lembar itu dan mengubah isinya. Kodenya harus
    dapat ditulis di tempat terbuka tanpa membawa serta kuncinya.
    """
    token = "MP0nC2irJt0aw3aa1JmdWYGsVVCiJa-euQ-ZeQ_kHG8"
    kode = kode_peserta(token)

    # Dibandingkan TANPA memedulikan besar-kecil huruf: `token[:6].upper()`
    # bukan kode yang aman, dan perbandingan yang peka huruf meloloskannya.
    assert kode.lower() not in token.lower()
    assert token[:6].lower() not in kode.lower()
    assert len(kode) == 6


def test_kode_peserta_tetap_sama_untuk_token_yang_sama():
    """HR dan pelamar harus selalu melihat kode yang sama."""
    assert kode_peserta("abc") == kode_peserta("abc")


def test_kode_peserta_berbeda_untuk_token_berbeda():
    assert kode_peserta("abc") != kode_peserta("abd")


def test_kode_peserta_kosong_tidak_meledak():
    assert kode_peserta("") == ""
    assert kode_peserta(None) == ""


# ---------------------------------------------------------------------
# Lembar jawaban.
# ---------------------------------------------------------------------


def _pelamar(**ubah):
    d = {
        "id": 5, "testID": 1, "name": "Budi", "gender": "L",
        "token": "tok", "status": "selesai", "startedAt": None,
        "submittedAt": None, "testName": "Ujian", "durationMinutes": 90,
    }
    d.update(ubah)
    return d


def _soal(qid, maks=5):
    return {
        "id": qid, "question": f"soal {qid}", "notes": None,
        "attachment": None, "category": "civil", "maxScore": maks,
        "allowsUpload": False, "sortOrder": qid,
    }


@pytest.mark.asyncio
async def test_soal_tanpa_jawaban_tetap_muncul(fake_db):
    """
    Kalau lembar disusun dari daftar `hr_answers`, soal yang tidak dijawab
    HILANG — dan yang memeriksa memberi nilai atas 2 soal lalu mengira itu
    seluruhnya, padahal paketnya 3.
    """
    db = fake_db(MODUL)
    db.queue("fetch_one", _pelamar())
    db.queue("fetch_all", [_soal(1), _soal(2), _soal(3)])
    db.queue("fetch_all", [
        {"id": 90, "questionID": 1, "answer": "jawab", "score": None,
         "checkerNote": None, "checkedAt": None, "checkedBy": None,
         "checkedByName": None},
    ])

    hasil = await HrRecruitmentRepository.lembar_jawaban(5)

    assert [s["questionID"] for s in hasil["soal"]] == [1, 2, 3]
    assert hasil["rekap"]["jumlahSoal"] == 3


@pytest.mark.asyncio
async def test_tidak_dijawab_dibedakan_dari_dijawab_kosong(fake_db):
    """
    `None` = soalnya tidak pernah disentuh. `""` = dibuka lalu dikosongkan.
    Keduanya bernilai nol, tetapi menyatakan hal berbeda tentang
    pengerjaannya — dan yang memeriksa memperlakukannya berbeda.
    """
    db = fake_db(MODUL)
    db.queue("fetch_one", _pelamar())
    db.queue("fetch_all", [_soal(1), _soal(2)])
    db.queue("fetch_all", [
        {"id": 90, "questionID": 1, "answer": "", "score": None,
         "checkerNote": None, "checkedAt": None, "checkedBy": None,
         "checkedByName": None},
    ])

    hasil = await HrRecruitmentRepository.lembar_jawaban(5)
    peta = {s["questionID"]: s for s in hasil["soal"]}

    assert peta[1]["answer"] == ""
    assert peta[2]["answer"] is None


@pytest.mark.asyncio
async def test_belum_dinilai_dihitung_terpisah_dari_nol(fake_db):
    """
    Nol adalah keputusan bahwa jawabannya salah; belum diperiksa adalah
    keadaan lain. Menyamakannya membuat lembar yang separuh diperiksa
    tampak sudah selesai dengan nilai rendah.
    """
    db = fake_db(MODUL)
    db.queue("fetch_one", _pelamar())
    db.queue("fetch_all", [_soal(1), _soal(2), _soal(3)])
    db.queue("fetch_all", [
        {"id": 90, "questionID": 1, "answer": "a", "score": 0,
         "checkerNote": None, "checkedAt": None, "checkedBy": None,
         "checkedByName": None},
        {"id": 91, "questionID": 2, "answer": "b", "score": None,
         "checkerNote": None, "checkedAt": None, "checkedBy": None,
         "checkedByName": None},
    ])

    r = (await HrRecruitmentRepository.lembar_jawaban(5))["rekap"]

    assert r["totalNilai"] == 0
    # Soal 2 (score None) dan soal 3 (tanpa baris sama sekali).
    assert r["belumDinilai"] == 2


@pytest.mark.asyncio
async def test_pelamar_tidak_ada_dijawab_404(fake_db):
    db = fake_db(MODUL)
    db.queue("fetch_one", None)

    hasil = await HrRecruitmentRepository.lembar_jawaban(999)

    assert hasil["status"] == 404


# ---------------------------------------------------------------------
# Menyimpan nilai.
# ---------------------------------------------------------------------


def _siap_nilai(fake_db, soal=((1, 5), (2, 5)), ada_baris=True):
    db = fake_db(MODUL)
    db.queue("fetch_one", {"id": 5, "testID": 1})
    db.queue("fetch_all", [{"id": q, "maxScore": m} for q, m in soal])
    for _ in range(10):
        db.queue("fetch_val", 90 if ada_baris else None)
    return db


def _perintah_tulis(db):
    """Pernyataan tulis terakhir, apa adanya."""
    for metode, kueri in reversed(db.calls):
        if metode == "execute":
            return kueri
    return None


def _nilai_ditulis(db):
    # `or ""` TIDAK boleh dipakai di sini: pernyataan SQLAlchemy menolak
    # dievaluasi sebagai boolean ("Boolean value of this clause is not
    # defined") dan melempar TypeError alih-alih jatuh ke cadangan.
    q = _perintah_tulis(db)
    return "" if q is None else str(q)


def _parameter(db):
    """
    Nilai yang BENAR-BENAR terikat pada pernyataannya.

    `db.last_values()` selalu None di sini: repository memanggil
    `database.execute(pernyataan)` dengan nilainya sudah menyatu di dalam
    pernyataan SQLAlchemy, bukan sebagai argumen kedua. Membacanya dari sana
    membuat pengujian ini HAMPA — ia lulus apa pun yang ditulis. Ketahuan
    saat sabotase "jejak pemeriksa tidak dicabut" tidak membuatnya merah.
    """
    q = _perintah_tulis(db)
    if q is None:
        return {}
    return dict(q.compile().params)


@pytest.mark.asyncio
async def test_nilai_melebihi_maksimum_ditolak(fake_db):
    """
    Batasnya dibaca dari basis data, bukan dipercaya dari muatan: tanpa itu,
    permintaan yang disusun sendiri dapat memberi 999 pada soal bernilai 5.
    """
    db = _siap_nilai(fake_db)

    hasil = await HrRecruitmentRepository.nilai_jawaban(
        5, [{"questionID": 1, "score": 999}], PEMERIKSA
    )

    assert hasil["tersimpan"] == 0
    assert hasil["ditolak"] == [1]


@pytest.mark.asyncio
async def test_nilai_negatif_ditolak(fake_db):
    db = _siap_nilai(fake_db)

    hasil = await HrRecruitmentRepository.nilai_jawaban(
        5, [{"questionID": 1, "score": -1}], PEMERIKSA
    )

    assert hasil["ditolak"] == [1]


@pytest.mark.asyncio
async def test_soal_paket_lain_ditolak(fake_db):
    """
    Nomor soal datang dari muatan. Tanpa penjagaan ini, nilai dapat
    dituliskan pada soal milik paket ujian lain — dan lembar pelamar lain
    ikut berubah tanpa ada yang melihatnya.
    """
    db = _siap_nilai(fake_db)

    hasil = await HrRecruitmentRepository.nilai_jawaban(
        5, [{"questionID": 77, "score": 3}], PEMERIKSA
    )

    assert hasil["tersimpan"] == 0
    assert hasil["ditolak"] == [77]


@pytest.mark.asyncio
async def test_nol_tersimpan_sebagai_nol(fake_db):
    db = _siap_nilai(fake_db)

    hasil = await HrRecruitmentRepository.nilai_jawaban(
        5, [{"questionID": 1, "score": 0}], PEMERIKSA
    )

    assert hasil["tersimpan"] == 1


@pytest.mark.asyncio
async def test_none_mencabut_penilaian_beserta_jejaknya(fake_db):
    """
    `None` membatalkan penilaian yang terlanjur keliru. Jejak pemeriksanya
    harus ikut dicabut: "diperiksa oleh X" pada baris tanpa nilai menyatakan
    pemeriksaan yang hasilnya tidak ada.
    """
    db = _siap_nilai(fake_db)

    await HrRecruitmentRepository.nilai_jawaban(
        5, [{"questionID": 1, "score": None}], PEMERIKSA
    )

    terikat = _parameter(db)
    assert "checkedBy" in terikat, terikat
    assert terikat["checkedBy"] is None
    assert terikat["checkedAt"] is None
    assert terikat["score"] is None


@pytest.mark.asyncio
async def test_menilai_soal_yang_belum_ada_barisnya_membuat_baris(fake_db):
    """
    Soal yang tidak dijawab tetap harus dapat dinilai — nol untuk yang
    dikosongkan adalah penilaian yang sah. Tanpa ini soal itu tidak dapat
    dinilai sama sekali.
    """
    db = _siap_nilai(fake_db, ada_baris=False)

    hasil = await HrRecruitmentRepository.nilai_jawaban(
        5, [{"questionID": 1, "score": 0}], PEMERIKSA
    )

    assert hasil["tersimpan"] == 1
    assert "INSERT INTO hr_answers" in _nilai_ditulis(db)


@pytest.mark.asyncio
async def test_baris_baru_tidak_menyebut_kolom_yang_tidak_ada(fake_db):
    """
    `hr_answers` TIDAK punya `createdAt` — hanya `updatedAt`.

    Menyebut kolom yang tidak ada membuat SQLAlchemy menolak seluruh
    pernyataan dengan "Unconsumed column names", galatnya tertelan `except`,
    dan jawabannya 500 tanpa menyebut sebabnya. Cacat yang persis seperti
    ini sudah ada di `expense_repository.approve`.
    """
    db = _siap_nilai(fake_db, ada_baris=False)

    hasil = await HrRecruitmentRepository.nilai_jawaban(
        5, [{"questionID": 1, "score": 1}], PEMERIKSA
    )

    assert "error" not in hasil, hasil
    assert "createdAt" not in _nilai_ditulis(db)


@pytest.mark.asyncio
async def test_pelamar_tidak_ada_dijawab_404_saat_menilai(fake_db):
    db = fake_db(MODUL)
    db.queue("fetch_one", None)

    hasil = await HrRecruitmentRepository.nilai_jawaban(
        999, [{"questionID": 1, "score": 1}], PEMERIKSA
    )

    assert hasil["status"] == 404
