"""
Pengacakan soal, dan ujian yang BOLEH DILANJUTKAN setelah tautannya
kedaluwarsa.

DUA KEPUTUSAN YANG MUDAH TERBALIK LAGI

1. Urutan soal diacak PER PELAMAR dan HARUS STABIL. Pengacakan yang berubah
   tiap panggilan jauh lebih buruk daripada tidak mengacak sama sekali:
   pelamar yang memuat ulang halamannya mendapat urutan baru, dan soal yang
   sedang ia kerjakan berpindah tempat di tengah kalimat.

2. Kedaluwarsa TAUTAN menentukan boleh-tidaknya MULAI, bukan boleh-tidaknya
   melanjutkan. Sebelumnya `simpan_jawaban` menyaring `expiresAt > now`
   polos, sehingga pelamar yang mulai sepuluh menit sebelum tautannya habis
   tetap melihat sisa 90 menit lalu kehilangan SELURUH jawabannya sesudah
   menit kesepuluh — tanpa satu pun tanda di layarnya, dan dengan IP-nya
   ikut terkunci lima belas menit oleh pembatas laju.

Yang membatasi lamanya mengerjakan adalah `durationMinutes`, dan itu
diperiksa terpisah lewat `sisa_waktu`.
"""

import os

from repository.hr_recruitment_repository import urutan_acak

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(AKAR, "repository", "hr_recruitment_repository.py")


def _soal(n=10):
    return [{"id": i, "sortOrder": i} for i in range(1, n + 1)]


def _blok(nama: str) -> str:
    s = open(REPO, encoding="utf-8").read()
    i = s.index(f"async def {nama}(")
    j = s.find("\n    @staticmethod", i)
    return s[i : j if j > 0 else len(s)]


# ---------------------------------------------------------------------
# Pengacakan.
# ---------------------------------------------------------------------


def test_urutan_sama_untuk_token_yang_sama():
    """
    Inilah yang membuat memuat ulang halaman aman. Tanpa ini, setiap
    penyegaran menyusun ulang ujiannya.
    """
    a = [x["id"] for x in urutan_acak(_soal(), "tok-A")]
    b = [x["id"] for x in urutan_acak(_soal(), "tok-A")]
    assert a == b


def test_urutan_berbeda_antar_pelamar():
    a = [x["id"] for x in urutan_acak(_soal(20), "tok-A")]
    b = [x["id"] for x in urutan_acak(_soal(20), "tok-B")]
    assert a != b


def test_tidak_ada_soal_yang_hilang_atau_ganda():
    """
    Pengacakan yang menghilangkan satu soal tidak menimbulkan galat apa pun
    — pelamarnya hanya mengerjakan 23 dari 24, dan yang memeriksa tidak
    punya cara tahu mengapa satu soal kosong.
    """
    asli = _soal(24)
    hasil = urutan_acak(asli, "tok-A")
    assert sorted(x["id"] for x in hasil) == sorted(x["id"] for x in asli)
    assert len(hasil) == len(asli)


def test_daftar_pendek_dan_token_kosong_tidak_meledak():
    assert urutan_acak([], "tok") == []
    assert [x["id"] for x in urutan_acak(_soal(1), "tok")] == [1]
    # Tanpa token, urutannya dibiarkan apa adanya — bukan melempar.
    assert [x["id"] for x in urutan_acak(_soal(5), "")] == [1, 2, 3, 4, 5]


def test_benih_tidak_memakai_hash_bawaan_python():
    """
    `hash()` untuk `str` diacak per proses (PYTHONHASHSEED), jadi urutannya
    akan berbeda setelah server di-restart — persis kegagalan yang hendak
    dicegah, hanya lebih jarang terlihat sehingga lebih sulit dipercaya
    ketika dilaporkan.
    """
    s = open(REPO, encoding="utf-8").read()
    blok = s[s.index("def urutan_acak(") : s.index("class HrRecruitmentRepository:")]
    assert "hashlib" in blok
    assert "hash(token)" not in blok


def test_soal_diacak_saat_ujian_dimulai():
    assert "urutan_acak(" in _blok("mulai_ujian")


# ---------------------------------------------------------------------
# Lembar penilaian TETAP urut aslinya.
# ---------------------------------------------------------------------


def test_lembar_penilaian_urut_sortorder():
    """
    Pelamar mengerjakan dalam urutan acak; yang MEMERIKSA harus selalu
    melihat urutan yang sama untuk semua pelamar. Tanpa ini, membandingkan
    jawaban nomor 7 antar-pelamar berarti membandingkan dua soal berbeda.
    """
    blok = _blok("lembar_jawaban")
    assert "order_by(hr_questions_table.c.sortOrder)" in blok
    assert "urutan_acak" not in blok


# ---------------------------------------------------------------------
# Lanjut mengerjakan setelah tautannya kedaluwarsa.
# ---------------------------------------------------------------------


def test_menyimpan_tidak_lagi_terhalang_kedaluwarsa_tautan():
    """
    Syaratnya harus `belum kedaluwarsa ATAU sudah pernah mulai`.
    """
    blok = _blok("simpan_jawaban")
    assert "or_(" in blok, (
        "syarat kedaluwarsa masih polos — pelamar yang mulai menjelang "
        "tautannya habis akan kehilangan seluruh jawabannya tanpa tanda "
        "apa pun di layarnya"
    )
    assert "startedAt.isnot(None)" in blok


def test_pintu_masuk_TETAP_menolak_tautan_kedaluwarsa():
    """
    Yang dilonggarkan hanya MELANJUTKAN. Membuka dan memulai ujian dengan
    tautan yang sudah lewat tetap harus ditolak — kalau tidak, masa berlaku
    tautan tidak berarti apa-apa.
    """
    for nama in ("pelamar_dari_token", "mulai_ujian"):
        blok = _blok(nama)
        assert "expiresAt > dt.now()" in blok, nama
        assert "startedAt.isnot(None)" not in blok, (
            f"{nama} ikut dilonggarkan — tautan yang sudah kedaluwarsa "
            f"tetap dapat dipakai memulai ujian baru"
        )


def test_batas_waktu_pengerjaan_tetap_ditegakkan():
    """
    Melonggarkan kedaluwarsa tautan TIDAK boleh ikut melonggarkan durasinya.
    """
    blok = _blok("simpan_jawaban")
    assert "sisa_waktu" in blok
    assert "sisa <= 0" in blok
