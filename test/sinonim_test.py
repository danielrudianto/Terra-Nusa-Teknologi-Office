"""
Sinonim pencarian katalog barang.

Disusun dari katalog sungguhan, dan angkanya disebut supaya yang meninjau
tahu ini bukan dugaan: `stanless` 191 kali berbanding `stainless` 31 —
yang mengeja dengan BENAR justru menemukan paling sedikit.
"""

from constants.sinonim_barang import (
    SINONIM,
    perluas_kata_kunci,
    punya_sinonim,
)


def test_kata_asli_selalu_ikut():
    """
    Pencarian yang kehilangan kata aslinya gagal menemukan barang yang
    namanya memang persis seperti yang diketik.
    """
    assert perluas_kata_kunci('xyzabc') == ['xyzabc']
    assert 'stainless' in perluas_kata_kunci('stainless')


def test_salah_eja_ikut_ditemukan():
    h = perluas_kata_kunci('stainless')
    assert 'stanless' in h
    # Dua arah: yang mengetik bentuk salahnya pun menemukan yang benar.
    assert 'stainless' in perluas_kata_kunci('stanless')


def test_dua_bahasa():
    assert 'kunci' in perluas_kata_kunci('wrench')
    assert 'wrench' in perluas_kata_kunci('kunci')
    assert 'kawat' in perluas_kata_kunci('wire')


def test_frasa_utuh_diperiksa_lebih_dulu():
    """
    "kuku macan" hanya bermakna sebagai frasa; memecahnya per kata
    menghasilkan "kuku" dan "macan" yang tidak berhubungan dengan apa pun.
    """
    h = perluas_kata_kunci('kuku macan')
    assert 'wire rope clip' in h
    # Kata per katanya tetap ikut, tetapi bukan itu yang menemukannya.
    assert h[0] == 'kuku macan'


def test_kalimat_diperluas_per_kata():
    h = perluas_kata_kunci('kunci ring stainless')
    assert 'wrench' in h
    assert 'stanless' in h


def test_kata_di_dua_kelompok_digabung():
    """
    `socket` ada pada kelistrikan DAN perkakas. Yang mengetiknya boleh
    bermaksud keduanya, sehingga keduanya digabung — bukan yang terakhir
    menang.
    """
    h = perluas_kata_kunci('socket')
    assert 'soket' in h
    assert 'stopkontak' in h or 'kunci sok' in h


def test_kosong_menghasilkan_kosong():
    assert perluas_kata_kunci('') == []
    assert perluas_kata_kunci('   ') == []


def test_punya_sinonim():
    assert punya_sinonim('stainless')
    assert not punya_sinonim('xyzabc')


def test_tidak_ada_kelompok_beranggota_satu():
    """
    Kelompok beranggota satu tidak berguna: ia tidak menghubungkan apa pun,
    dan hanya memperlambat penyusunan petanya.
    """
    tunggal = [k for k in SINONIM if len(k) < 2]
    assert not tunggal, tunggal


def test_seluruh_anggota_huruf_kecil():
    """
    Petanya dicocokkan dalam huruf kecil; anggota berhuruf besar tidak akan
    pernah ditemukan.
    """
    salah = [k for kel in SINONIM for k in kel if k != k.lower()]
    assert not salah, salah
