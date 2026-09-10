"""
Kemajuan proyek: yang dijaga dan yang sengaja TIDAK dijaga.

Angka ini dibaca sebagai kurva, bukan sebagai daftar. Itu yang menentukan
aturannya:

  * Dua baris pada satu tanggal membuat kurvanya bercabang, dan tidak ada cara
    membaca mana yang benar — ditolak.
  * Persen di luar 0-100 membuat sumbunya melar dan seluruh kurva lain
    gepeng — ditolak.
  * Angka yang TURUN dibiarkan. Pekerjaan yang harus diulang memang mengurangi
    kemajuan; memaksanya naik terus menyembunyikan persoalan yang paling
    mahal.

Diperiksa dari sumbernya untuk aturan yang berupa urutan dan syarat, dan
dijalankan sungguhan untuk yang berupa perhitungan.
"""

import os
import re

from schemas.project_schema import ProgressCreate, ProgressUpdate

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTRL = "controllers/project_progress_controller.py"
REPO = "repository/project_progress_repository.py"


def _blok(relatif: str, nama: str) -> str:
    s = open(os.path.join(AKAR, relatif), encoding="utf-8").read()
    i = s.index(f"async def {nama}(")
    j = s.find("async def ", i + 10)
    blok = s[i:] if j == -1 else s[i:j]
    return "\n".join(
        b for b in blok.splitlines() if not b.lstrip().startswith("#")
    )


# ----------------------------------------------------------------------
# Skema
# ----------------------------------------------------------------------

def test_persen_di_luar_batas_ditolak():
    for buruk in (-1, 100.01, 1000):
        try:
            ProgressCreate(date="2026-09-01", percentage=buruk)
        except Exception:
            continue
        raise AssertionError(f"persen {buruk} seharusnya ditolak")


def test_persen_di_dalam_batas_diterima():
    for baik in (0, 0.5, 42.75, 100):
        ProgressCreate(date="2026-09-01", percentage=baik)


def test_kemajuan_boleh_turun():
    """
    Bukan kelalaian — ini keputusan.

    Pekerjaan yang harus diulang mengurangi kemajuan. Skema yang memaksa
    angkanya naik terus akan membuat kurva tetap rapi justru pada proyek yang
    sedang bermasalah.
    """
    ProgressUpdate(percentage=10)
    ProgressUpdate(percentage=90)


def test_penyuntingan_sebagian_tidak_menuntut_seluruh_bidang():
    """`exclude_unset` di rutenya hanya berguna bila bidangnya opsional."""
    hanya_persen = ProgressUpdate(percentage=55).model_dump(exclude_unset=True)
    assert set(hanya_persen) == {"percentage"}


# ----------------------------------------------------------------------
# Controller
# ----------------------------------------------------------------------

def test_satu_tanggal_satu_catatan():
    b = _blok(CTRL, "create_progress")
    assert "ada_pada_tanggal" in b, "tanggal ganda tidak diperiksa"
    assert "PROGRESS_DATE_EXISTS" in b, (
        "penolakannya tidak memakai kode tetap, sehingga layar tidak dapat "
        "menerjemahkannya menjadi kalimat yang berguna"
    )


def test_menyunting_tanggal_juga_diperiksa():
    """
    Memindahkan sebuah catatan ke tanggal yang sudah terisi menghasilkan
    percabangan yang sama dengan membuat catatan ganda.
    """
    b = _blok(CTRL, "update_progress")
    assert "ada_pada_tanggal" in b
    assert "kecuali_id=progress_id" in b, (
        "pemeriksaannya tidak mengecualikan baris yang sedang disunting, "
        "sehingga menyimpan tanpa mengubah tanggal pun akan ditolak"
    )


def test_proyeknya_diperiksa_ada():
    b = _blok(CTRL, "create_progress")
    assert "ProjectRepository.get_by_id" in b, (
        "kemajuan dapat dicatat pada proyek yang tidak ada"
    )


def test_baris_terhapus_tidak_dapat_disunting_atau_dihapus_lagi():
    for fn in ("update_progress", "delete_progress"):
        b = _blok(CTRL, fn)
        assert 'baris["isDelete"]' in b, f"{fn} tidak menolak baris terhapus"


# ----------------------------------------------------------------------
# Repository
# ----------------------------------------------------------------------

def test_riwayat_terurut_naik():
    """
    Yang membacanya bukan mencari baris terbaru melainkan membaca kurva, dan
    kurva yang datang terbalik harus dibalik lagi di layar.
    """
    b = _blok(REPO, "list_by_project")
    assert re.search(r"c\.date\.asc\(\)", b), "riwayat tidak terurut naik"


def test_baris_terhapus_tidak_menghalangi_pencatatan_ulang():
    """
    Inilah sebabnya tanggal ganda dijaga di sini, bukan oleh indeks unik.

    Indeks unik tidak dapat membedakan baris hidup dari baris terhapus, dan
    akan menolak pencatatan ulang pada tanggal yang catatannya sudah dihapus.
    """
    b = _blok(REPO, "ada_pada_tanggal")
    assert "isDelete == False" in b, (
        "baris terhapus ikut dihitung, sehingga tanggalnya terkunci selamanya"
    )


def test_gagal_memeriksa_dianggap_tanggalnya_terisi():
    b = _blok(REPO, "ada_pada_tanggal")
    assert "return True" in b.split("except")[-1], (
        "kegagalan memeriksa meloloskan dua baris pada satu tanggal"
    )


def test_setiap_perubahan_meninggalkan_jejak():
    for fn in ("create", "update", "delete"):
        b = _blok(REPO, fn)
        assert 'entity="project_progress"' in b, f"{fn} tidak mencatat jejak"
    assert "AuditLogRepository.diff" in _blok(REPO, "update"), (
        "jejak penyuntingan tidak menyebut dari apa menjadi apa"
    )


# ----------------------------------------------------------------------
# Izin
# ----------------------------------------------------------------------

def test_modul_izinnya_terpisah_dari_project():
    """
    Nilai kontrak diubah level 4; kemajuan dicatat orang lapangan. Satu modul
    untuk keduanya memaksa memilih salah satu kekeliruan.
    """
    from constants.permission_matrix import MATRIX

    assert "project_progress" in MATRIX
    baca, buat, ubah, hapus, setuju = MATRIX["project_progress"]
    assert buat <= 2, "mencatat kemajuan tidak terjangkau orang lapangan"
    assert MATRIX["project"][1] >= 4, "asumsi tentang modul project berubah"
    assert setuju == 0, "kemajuan tidak punya alur persetujuan"


def test_modulnya_punya_wilayah():
    """
    Pemeriksaan wilayah divisi berjalan LEBIH DAHULU daripada level. Modul
    tanpa wilayah ditolak untuk semua orang yang punya divisi, berapa pun
    levelnya — sementara yang tidak punya divisi justru lolos.
    """
    from constants.department_modules import DEPARTMENT_MODULES

    punya = {d for d, m in DEPARTMENT_MODULES.items() if "project_progress" in m}
    assert "engineering" in punya, "engineering tidak dapat mencatat kemajuan"
    assert "fat" in punya, "keuangan tidak dapat membaca kemajuan di laporan proyek"
