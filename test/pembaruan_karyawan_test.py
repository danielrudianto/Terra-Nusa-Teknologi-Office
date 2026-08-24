"""
Pembaruan data karyawan: riwayat, bukan penimpaan.

Pembaruan dapat dilakukan KAPAN SAJA. Yang berlaku adalah yang terakhir, dan
yang sebelumnya tetap tersimpan — alamat lama, jumlah tanggungan sebelumnya,
dan kapan tiap keadaan itu berlaku.

Bila data tidak diperbarui lebih dari satu tahun, HRD perlu menanyakan dan
menyimpannya ulang. Menyimpan ulang TANPA mengubah apa pun tetap dihitung:
yang dikonfirmasi bukan datanya berubah, melainkan bahwa datanya masih benar.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _blok(berkas: str, nama: str) -> str:
    s = open(os.path.join(AKAR, berkas)).read()
    i = s.index(f"async def {nama}(")
    j = s.find("async def ", i + 10)
    return s[i:] if j == -1 else s[i:j]


def test_menyimpan_selalu_menambah_baris():
    """
    Tanpa baris per penyimpanan, tidak ada tanggal yang dapat dibandingkan —
    dan "sudah setahun tidak diperbarui" tidak dapat dihitung sama sekali.
    """
    b = _blok("repository/employee_form_repository.py", "save_submission")
    assert "insert(employee_form_submissions_table)" in b
    assert "update(employee_form_submissions_table)" not in b


def test_yang_dibaca_adalah_yang_terbaru():
    """
    Satu karyawan kini punya banyak baris. Tanpa pengurutan, basis data bebas
    mengembalikan yang mana pun — dan layar dapat menampilkan alamat lama
    sebagai keadaan sekarang.
    """
    b = _blok("repository/employee_form_repository.py", "get_submission")
    assert "submittedAt.desc()" in b
    assert "limit(1)" in b


def test_profil_ikut_dihitung_sebagai_pembaruan():
    """
    Mengisi PROFIL PRIBADI juga menghentikan hitungan setahunnya.

    Profil dan formulir keadaan sama-sama data karyawan; memisahkannya
    membuat orang yang profilnya baru diisi tetap tertagih seolah belum
    pernah menyentuh datanya sama sekali.

    `updatedAt` bernilai NULL sampai ada penyuntingan pertama, sehingga
    `createdAt` dipakai sebagai cadangannya — pengisian pertama pun sebuah
    peninjauan data.
    """
    b = _blok("repository/employee_form_repository.py", "kedaluwarsa")
    assert "employee_profiles" in b
    assert "COALESCE(p.updatedAt, p.createdAt" in b
    assert "GREATEST(" in b


def test_kedaluwarsa_menyertakan_yang_belum_pernah():
    """
    Yang belum pernah mengisi memerlukan tindakan yang sama dengan yang sudah
    kedaluwarsa; memisahkannya membuat HRD harus membuka dua daftar.
    """
    b = _blok("repository/employee_form_repository.py", "kedaluwarsa")
    assert "terakhir IS NULL" in b


def test_kedaluwarsa_mengecualikan_yang_sudah_keluar():
    """Menanyakan data orang yang tidak lagi bekerja tidak ada gunanya."""
    b = _blok("repository/employee_form_repository.py", "kedaluwarsa")
    assert "e.endDate IS NULL" in b


def test_batas_setahun_dan_jangkauan_tiga_puluh_hari():
    """
    Muncul tiga puluh hari SEBELUM jatuh tempo, bukan tujuh seperti ulang
    tahun: mengumpulkan data karyawan perlu menghubungi orangnya dan kerap
    menunggu ia pulang dari lapangan.
    """
    b = _blok("repository/employee_form_repository.py", "kedaluwarsa")
    assert "batas_bulan: int = 12" in b
    assert "jangkauan_hari: int = 30" in b

    s = open(os.path.join(AKAR, "controllers", "agenda_controller.py")).read()
    assert "batas_bulan=12" in s
    assert "jangkauan_konfirmasi: int = 30" in s


def test_agenda_tidak_jatuh_bila_konfirmasi_gagal():
    """
    Agenda memuat beberapa hal yang tidak berkaitan; satu yang gagal tidak
    boleh mengosongkan seluruh halaman.
    """
    s = open(os.path.join(AKAR, "controllers", "agenda_controller.py")).read()
    i = s.index("konfirmasi = []")
    j = s.index("return {", i)
    blok = s[i:j]
    assert "try:" in blok and "except Exception" in blok


def test_riwayat_terbaru_lebih_dulu():
    b = _blok("repository/employee_form_repository.py", "riwayat")
    assert "ORDER BY s.submittedAt DESC" in b
