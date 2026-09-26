"""
Batas akses FAT terhadap Certificate of Payment.

FAT-lah yang menerbitkan PEMBELIAN untuk menagihkan sebuah CoP yang sudah
disetujui, dan formulir pembelian menawarkan "isi dari CoP" hanya kepada yang
boleh MEMBACA modul ini. Karena itu FAT harus dapat membaca CoP —

  tetapi TIDAK membuat, memeriksa, maupun menyetujuinya. Ketiganya tetap
  wilayah engineering.

Cerminan dari hubungan engineering↔purchase_order, arah sebaliknya:
engineering membaca SPK untuk menyusun CoP tanpa menerbitkan PO; FAT membaca
CoP untuk menerbitkan pembelian tanpa menyusun CoP.

Pengujian ini memanggil `is_allowed` YANG SEBENARNYA. Aturan yang disalin ke
berkas uji tetap lulus ketika yang asli berubah — dan justru saat itulah
pengujian ini paling dibutuhkan.
"""

import asyncio
import time

import pytest

from utils import permission as izin_modul
from utils.permission import is_allowed

MODUL = "certificate_of_payment"


def _pengguna(user_id: int, level: int, divisi: set[str], khusus=None):
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


def test_cop_menjadi_wilayah_fat_dan_engineering():
    from constants.department_modules import DEPARTMENT_MODULES

    pemilik = sorted(k for k, v in DEPARTMENT_MODULES.items() if MODUL in v)
    assert pemilik == ["engineering", "fat"], pemilik


def test_fat_boleh_membaca_cop():
    """
    Inilah yang menyalakan pilihan "isi dari CoP" pada formulir pembelian.
    Tanpanya, divisi yang menjalankan penagihannya justru tidak melihatnya.
    """
    assert boleh(3, 3, {"fat"}, "read") is True


def test_fat_tidak_boleh_menyunting_cop():
    """
    Hanya-baca, sama seperti procurement atas aset. Membuat, mengubah,
    menghapus, dan menyetujui CoP tetap wilayah engineering.
    """
    for aksi in ("create", "update", "delete", "approve"):
        assert boleh(3, 3, {"fat"}, aksi) is False, aksi


def test_engineering_tetap_penuh():
    """Perubahan untuk FAT tidak boleh menyentuh akses engineering."""
    assert boleh(2, 2, {"engineering"}, "read") is True
    assert boleh(2, 2, {"engineering"}, "create") is True
    assert boleh(2, 2, {"engineering"}, "update") is True


def test_divisi_lain_tanpa_izin_tetap_tertutup():
    """
    Procurement tidak menyentuh CoP sama sekali — tidak membuat pembelian
    penagih, tidak pula menyusun CoP.
    """
    assert boleh(3, 3, {"procurement"}, "read") is False
