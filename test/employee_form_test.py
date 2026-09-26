"""
Susunan formulir keadaan karyawan.

Definisi yang salah harus ditolak SAAT versinya dibuat, bukan saat karyawan
sudah membuka formulirnya dan menemukan isian yang tidak muncul — pada titik
itu tidak ada galat apa pun, hanya pertanyaan yang hilang.
"""

import copy
import os

os.environ.setdefault("DATABASE_URL", "mysql://uji:uji@localhost/uji")

from constants.employee_form_default import (  # noqa: E402
    FORMULIR_BAWAAN,
    JENIS_ISIAN,
    periksa_definisi,
)


def test_formulir_bawaan_sah():
    assert periksa_definisi(FORMULIR_BAWAAN) == []


def test_bawaan_hanya_memuat_yang_berubah():
    """
    Data yang menempel pada orangnya tidak ditanyakan ulang.

    Pendidikan formal dan pengalaman kerja sebelum masuk ada di profil.
    Menanyakannya tiap tahun membuat karyawan mengetik ulang sebagian besar
    formulir, dan yang terjadi kemudian adalah pengisian asal.
    """
    kunci = {
        f["key"]
        for b in FORMULIR_BAWAAN["sections"]
        for f in b["fields"]
    }
    for statis in ("formalEducation", "workExperience", "motherName", "ktpNumber"):
        assert statis not in kunci, statis


def test_kontak_darurat_ada():
    """Bagian yang paling berbahaya bila basi; tidak boleh hilang."""
    bagian = {b["key"] for b in FORMULIR_BAWAAN["sections"]}
    assert "darurat" in bagian


def test_jenis_tidak_dikenali_ditolak():
    rusak = copy.deepcopy(FORMULIR_BAWAAN)
    rusak["sections"][0]["fields"][0]["type"] = "salahketik"
    assert periksa_definisi(rusak)


def test_kunci_ganda_lintas_bagian_ditolak():
    """
    Jawaban disimpan datar, sehingga dua isian berkunci sama saling menimpa
    tanpa galat apa pun — dan yang hilang baru ketahuan saat dibaca.
    """
    rusak = copy.deepcopy(FORMULIR_BAWAAN)
    rusak["sections"][1]["fields"][0]["key"] = rusak["sections"][0]["fields"][0]["key"]
    masalah = periksa_definisi(rusak)
    assert any("dua kali" in m for m in masalah)


def test_pilih_tanpa_opsi_ditolak():
    rusak = copy.deepcopy(FORMULIR_BAWAAN)
    rusak["sections"][0]["fields"][0].pop("options")
    assert periksa_definisi(rusak)


def test_daftar_tanpa_kolom_ditolak():
    rusak = copy.deepcopy(FORMULIR_BAWAAN)
    for f in rusak["sections"][0]["fields"]:
        if f["type"] == "daftar":
            f.pop("columns")
            break
    assert periksa_definisi(rusak)


def test_formulir_kosong_ditolak():
    assert periksa_definisi({"sections": []})
    assert periksa_definisi({})


def test_seluruh_jenis_terpakai_dikenali():
    """Definisi bawaan tidak boleh memakai jenis di luar yang dikenali layar."""
    for b in FORMULIR_BAWAAN["sections"]:
        for f in b["fields"]:
            assert f["type"] in JENIS_ISIAN, f["key"]
