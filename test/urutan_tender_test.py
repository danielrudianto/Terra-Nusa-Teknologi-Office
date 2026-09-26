"""
Pengurutan daftar tender.

Daftar tender sebelumnya selalu terurut `id` menurun dan tidak dapat diubah,
sementara daftar Pembelian dan Reimbursement — yang dibuka orang yang sama
dalam satu hari — judul kolomnya dapat ditekan untuk mengurutkan.

Dua hal yang dijaga di sini, dan keduanya tidak terlihat dari layar:

  1. Nama kolom yang datang dari luar TIDAK diteruskan apa adanya ke
     `ORDER BY`. Daftarnya tertutup, dan yang tidak dikenal jatuh ke urutan
     lama — bukan menghasilkan galat, dan bukan pula membuka kolom yang tidak
     dimaksudkan untuk dibaca.

  2. `quoteCount` tidak dapat dipakai mengurutkan. Ia dihitung SESUDAH
     barisnya diambil, sehingga mengurutkan dengannya hanya akan mengurutkan
     halaman yang sedang tampil — daftarnya terlihat mengurut padahal tidak.
"""

import pytest

from models.tender_model import tenders_table
from repository.tender_repository import TenderRepository

MODUL = "repository.tender_repository"


def _urutan(sortBy=None, arah="desc") -> str:
    return str(TenderRepository._urutan(sortBy, arah))


def test_tanpa_pengurutan_tetap_seperti_dahulu():
    """
    Cadangannya `id` menurun — urutan yang berlaku sebelum ini ada.

    Cadangan yang berbeda membuat daftar yang dibuka tanpa memilih apa pun
    berubah susunannya, dan yang membukanya menyangka datanya bergeser.
    """
    assert "id" in _urutan()
    assert "DESC" in _urutan().upper()


def test_kolom_yang_dikenal_dipakai():
    assert "name" in _urutan("name", "asc")
    assert "ASC" in _urutan("name", "asc").upper()
    assert "dueDate" in _urutan("dueDate", "desc")


def test_kolom_yang_TIDAK_dikenal_jatuh_ke_cadangan():
    """Bukan galat, dan bukan pula kolom sembarang."""
    for ngawur in ("password", "createdBy", "", "id; DROP TABLE tenders"):
        hasil = _urutan(ngawur)
        assert "id" in hasil, ngawur
        assert "DROP" not in hasil.upper(), ngawur


def test_quoteCount_TIDAK_dapat_mengurutkan():
    """
    Ia dihitung sesudah barisnya diambil.

    Mengurutkan dengannya hanya menyusun ulang halaman yang sedang tampil —
    dan itu lebih menyesatkan daripada tidak dapat mengurutkan sama sekali,
    sebab kolomnya terlihat menanggapi.
    """
    assert "quoteCount" not in TenderRepository.SORTABLE
    assert "id" in _urutan("quoteCount")


def test_seluruh_kolom_yang_diizinkan_memang_ada_di_tabel():
    """
    Penjaga terhadap salah ketik.

    Nama yang keliru pada peta ini tidak menimbulkan galat: ia hanya tidak
    pernah cocok, sehingga kolomnya diam-diam tidak dapat diurutkan
    sementara judulnya di layar tetap dapat ditekan.
    """
    kolom_tabel = {c.name for c in tenders_table.columns}
    for nama, kolom in TenderRepository.SORTABLE.items():
        assert kolom.name in kolom_tabel, nama


def test_arah_selain_asc_dianggap_menurun():
    # Nilai yang tidak dikenal tidak boleh membalik artinya diam-diam.
    for arah in ("desc", "DESC", "", None, "ngawur"):
        assert "DESC" in _urutan("name", arah).upper(), arah


def test_arah_asc_tidak_bergantung_besar_kecil_huruf():
    for arah in ("asc", "ASC", "Asc"):
        assert "ASC" in _urutan("name", arah).upper(), arah


@pytest.mark.asyncio
async def test_pengurutan_ikut_terpasang_pada_kuerinya(fake_db):
    """
    Penjaga bahwa urutannya benar-benar sampai ke kueri datanya.

    Peta yang benar tetapi tidak pernah dipakai adalah keadaan yang paling
    sukar dikenali: pengujian atas petanya lulus, dan daftarnya tetap terurut
    seperti dahulu.
    """
    db = fake_db(MODUL)
    db.queue("fetch_val", 0)
    db.queue("fetch_all", [])

    await TenderRepository.daftar(sortBy="name", sortByDirection="asc")

    kueri = " ".join(str(q) for m, q in db.calls if m == "fetch_all")

    # HANYA bagian ORDER BY-nya yang diperiksa.
    #
    # Percobaan pertama memeriksa seluruh teks kuerinya, dan pernyataannya
    # lulus karena `name` memang tercantum sebagai kolom yang DIPILIH —
    # bukan karena ia dipakai mengurutkan. Penjaganya lulus sekalipun
    # urutannya dikembalikan ke bentuk lama.
    atas = kueri.upper()
    assert "ORDER BY" in atas
    bagian_urutan = kueri[atas.index("ORDER BY") :]
    assert "name" in bagian_urutan, bagian_urutan
    assert "ASC" in bagian_urutan.upper(), bagian_urutan
