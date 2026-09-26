"""
Batas akses modul aset.

Aset menjadi urusan DUA divisi dengan kedalaman yang berbeda: procurement
perlu mengetahui perusahaan punya alat apa saja sebelum memutuskan menyewa
atau membeli, sedangkan yang mencatat perolehan, menghitung penyusutan, dan
menyesuaikan nilainya saat dilepas adalah accounting — dan angka itu masuk ke
pembukuan.

Pengujian ini memanggil `is_allowed` YANG SEBENARNYA, bukan menyalin ulang
aturannya. Aturan yang disalin ke berkas uji akan tetap lulus ketika yang asli
berubah, dan justru pada saat itulah pengujian ini paling dibutuhkan.

Pembacaan izin khusus dan divisi dilewati dengan mengisi cache modulnya
langsung, sehingga tidak ada satu pun kueri yang dijalankan.
"""

import asyncio
import time

import pytest

from utils import permission as izin_modul
from utils.permission import is_allowed

MODUL = "asset"


def _pengguna(user_id: int, level: int, divisi: set[str], khusus=None):
    """
    Pengguna tiruan beserta cache izin dan divisinya.

    Cache diisi dengan stempel waktu SEKARANG agar dianggap masih berlaku;
    tanpa itu `is_allowed` jatuh ke basis data yang tidak ada di pengujian.
    """
    sekarang = time.monotonic()
    izin_modul._CACHE[user_id] = (sekarang, khusus or {})
    izin_modul._DEPT_CACHE[user_id] = (sekarang, set(divisi))
    return {"id": user_id, "authenticationLevel": level}


def boleh(user_id, level, divisi, aksi, khusus=None) -> bool:
    pengguna = _pengguna(user_id, level, divisi, khusus)
    return asyncio.run(is_allowed(pengguna, MODUL, aksi))


@pytest.fixture(autouse=True)
def _bersihkan_cache():
    izin_modul.invalidate_permission_cache()
    yield
    izin_modul.invalidate_permission_cache()


def test_aset_menjadi_wilayah_fat_dan_procurement():
    from constants.department_modules import DEPARTMENT_MODULES

    pemilik = sorted(k for k, v in DEPARTMENT_MODULES.items() if MODUL in v)
    # `konsultan` menyusul, dan HANYA-BACA — penyusutan aset masuk ke laba
    # rugi, sehingga angkanya perlu ditelusuri sampai ke daftar asetnya.
    #
    # Ia tidak mengubah apa pun; dijaga `test_konsultan_tidak_mencatat_aset`
    # di bawah, dan oleh `DEPARTMENT_READ_ONLY` di peta wilayahnya.
    assert pemilik == ["fat", "konsultan", "procurement"], pemilik


def test_konsultan_tidak_mencatat_aset():
    """
    Konsultan membaca aset, tetapi tidak menyentuhnya.

    Bedanya dengan accounting justru di sinilah: keduanya membuka daftar
    yang sama, tetapi yang mencatat perolehan dan menyesuaikan nilainya
    hanya orang dalam. Angka penyusutan masuk ke pembukuan, dan pembukuan
    tidak boleh berubah oleh tangan pihak luar.
    """
    assert boleh(111, 3, {"konsultan"}, "read")
    assert not boleh(112, 3, {"konsultan"}, "create")
    assert not boleh(113, 3, {"konsultan"}, "update")
    assert not boleh(114, 3, {"konsultan"}, "delete")


def test_accounting_boleh_membaca_membuat_mengubah():
    """
    Inti permintaannya: accounting level 3 harus dapat memeriksa, mencatat,
    dan mengubah aset.
    """
    assert boleh(101, 3, {"fat"}, "read")
    assert boleh(102, 3, {"fat"}, "create")
    assert boleh(103, 3, {"fat"}, "update")


def test_staf_accounting_boleh_melihat_tetapi_tidak_mengubah():
    """Level 1 dan 2 melihat daftarnya; batasnya dijaga matriks, bukan divisi."""
    assert boleh(111, 1, {"fat"}, "read")
    assert not boleh(112, 1, {"fat"}, "create")
    assert not boleh(113, 2, {"fat"}, "update")


def test_procurement_hanya_membaca():
    """
    Procurement perlu melihat perusahaan punya apa saja — tidak lebih.
    Sebelum aturan hanya-baca ada, level 3 di sini lolos `create` dan
    `update` karena matriksnya memang menetapkan 3.
    """
    assert boleh(121, 1, {"procurement"}, "read")
    assert boleh(122, 3, {"procurement"}, "read")
    assert not boleh(123, 3, {"procurement"}, "create")
    assert not boleh(124, 3, {"procurement"}, "update")


def test_izin_khusus_tetap_menang_atas_hanya_baca():
    """
    Satu orang procurement yang memang perlu mencatat dapat diberi haknya
    tanpa mengubah kebijakan bagi seluruh divisinya.
    """
    assert boleh(
        131,
        3,
        {"procurement"},
        "create",
        khusus={(MODUL, "create"): True},
    )


def test_dua_divisi_memperoleh_yang_terluas():
    """
    Orang yang menangani procurement DAN accounting tidak boleh ikut terkunci
    oleh batas procurement — `modules_for` pun menggabungkan, bukan mengiris.
    """
    assert boleh(141, 3, {"procurement", "fat"}, "create")
    assert boleh(142, 3, {"fat", "procurement"}, "update")


def test_divisi_lain_tetap_tertutup():
    assert not boleh(151, 3, {"hrd"}, "read")


def test_level_tinggi_tidak_dibatasi_divisi():
    """
    General manager dan pemilik berwenang atas seluruh perusahaan; batas
    wilayah maupun aturan hanya-baca sengaja tidak berlaku bagi mereka.
    """
    assert boleh(161, 4, {"procurement"}, "create")
    assert boleh(162, 5, set(), "update")


def test_hapus_tetap_level_empat():
    """Matriks tidak diubah: hapus tetap milik level 4 ke atas."""
    assert not boleh(171, 3, {"fat"}, "delete")
    assert boleh(172, 4, {"fat"}, "delete")
