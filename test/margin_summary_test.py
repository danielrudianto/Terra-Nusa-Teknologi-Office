"""
Ikhtisar margin proyek.

Yang dijaga di sini bukan angkanya — itu berasal dari basis data — melainkan
BENTUK kuerinya. Satu kesalahan bentuk mengubah tabel ini dari ringan menjadi
tidak dapat dipakai, dan gejalanya baru terlihat setelah proyeknya banyak.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMBER = open(os.path.join(AKAR, "repository", "project_repository.py")).read()


def _kueri() -> str:
    i = SUMBER.index("async def ringkasan_margin")
    j = SUMBER.index("async def add_contract", i)
    return SUMBER[i:j]


def test_dijumlahkan_di_basis_data():
    """
    Tiap sumber biaya dijumlahkan dengan GROUP BY, bukan ditarik utuh.

    Tanpa ini, tabel ikhtisar mengulang persoalan laporan per proyek: empat
    kumpulan baris utuh per proyek, dikirim ke peramban hanya untuk menjadi
    satu angka.
    """
    k = _kueri()
    assert k.count("GROUP BY") >= 4, "tidak semua sumber dijumlahkan di basis data"
    assert k.count("SUM(") >= 4


def test_halaman_dikunci_sepuluh():
    """
    Batas halaman tidak boleh dapat dinaikkan pemanggilnya.

    Tiap baris berasal dari empat penjumlahan lintas tabel; membuka batasnya
    mengembalikan beban yang justru hendak dihindari.
    """
    k = _kueri()
    assert "min(10," in k, "page_size tidak dibatasi sepuluh"
    assert "LIMIT :limit" in k and "OFFSET :offset" in k


def test_yang_berjalan_didahulukan():
    """Proyek berjalan lebih dahulu: di situ marginnya masih dapat diperbaiki."""
    assert "ORDER BY p.isActive DESC" in _kueri()


def test_hapus_lunak_disaring_di_setiap_sumber():
    """
    Setiap sumber menyaring `isDelete`.

    Satu sumber yang terlewat membuat biaya yang sudah dihapus tetap
    terhitung — dan margin yang salah di sini tidak menimbulkan galat apa
    pun, hanya angka yang keliru.
    """
    k = _kueri()
    assert k.count("isDelete = 0") >= 5, "ada sumber tanpa saringan hapus lunak"


def test_draft_ikut_sebagai_biaya():
    """
    Draft pembelian dihitung sebagai biaya.

    Draft belum tentu menjadi pembelian, tetapi biaya yang belum tercatat
    yang paling berbahaya: tanpanya proyek tampak untung padahal tagihannya
    belum masuk semua.
    """
    k = _kueri()
    assert "beli + draft + reimburse" in k


def test_dua_margin_berbeda_perlakuan_internal():
    """Margin dengan dan tanpa pembelian internal harus dihitung terpisah."""
    k = _kueri()
    assert "marginInternalMasuk" in k and "marginInternalKeluar" in k
    assert "total_biaya - internal" in k


def test_kontrak_memakai_dpp():
    """
    Nilai kontrak memakai DPP, bukan nominal kotor.

    Membandingkan biaya yang DPP dengan kontrak yang sudah termasuk PPN
    membuat margin setiap proyek tampak lebih besar daripada sebenarnya.
    Keputusan ini sudah berlaku pada laporan per proyek; keduanya harus sama
    agar angkanya dapat dibandingkan.
    """
    k = _kueri()
    assert re.search(r"SUM\(dpp\)\s+AS kontrak", k)
