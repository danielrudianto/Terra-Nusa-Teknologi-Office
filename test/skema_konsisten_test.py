"""
Skema harus dapat dibangun ULANG dari nol.

Ini bukan soal kerapian. Basis data produksi sudah punya seluruh tabelnya
sejak lama, jadi model yang tidak konsisten tetap melayani permintaan
sehari-hari tanpa satu pun keluhan. Yang hilang adalah kemampuan MEMULIHKAN:
`metadata.create_all` menolak berjalan bila satu saja foreign key menunjuk
tabel yang tidak terdaftar, dan penolakannya total — bukan satu tabel yang
gagal, melainkan seluruhnya.

Persis itu yang terjadi: `salary_slips.userID` menunjuk `employee`, sedangkan
nama tabelnya `employees`. Akibatnya `startup/create_tables.py` tidak pernah
dapat dijalankan, dan skema ini hanya hidup di satu tempat — mesin produksi
dan cadangannya. Tidak ada yang tahu, karena tidak ada yang pernah
memerlukannya sampai hari basis datanya hilang.

Uji di sini murah dan tidak menyentuh basis data: model diimpor, lalu
tautannya diperiksa terhadap daftar tabel yang benar-benar terdaftar.
"""

import glob
import importlib
import os
import sys

import pytest

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _muat_semua_model():
    """
    Impor seluruh `models/*_model.py`, lalu kembalikan metadata bersamanya.

    `balance` dan `mutation` dilewati: keduanya VIEW yang dibaca dari basis
    data saat modulnya di-import (`autoload_with`), dan conftest sudah
    menggantinya dengan tabel tiruan pada pengujian tanpa basis data.
    """
    if AKAR not in sys.path:
        sys.path.insert(0, AKAR)

    from utils.database import metadata

    gagal = []
    for berkas in sorted(glob.glob(os.path.join(AKAR, "models", "*_model.py"))):
        nama = "models." + os.path.basename(berkas)[:-3]
        if nama in sys.modules:
            continue
        try:
            importlib.import_module(nama)
        except Exception as e:  # noqa: BLE001
            gagal.append((nama, str(e)))
    return metadata, gagal


def test_setiap_berkas_model_dapat_diimpor():
    """
    Satu modul model yang gagal di-import menjatuhkan seluruh aplikasi saat
    dinyalakan, bukan hanya satu halaman.
    """
    _, gagal = _muat_semua_model()
    assert not gagal, "modul model gagal di-import:\n  " + "\n  ".join(
        f"{n}: {p}" for n, p in gagal
    )


def test_setiap_foreign_key_menunjuk_tabel_yang_terdaftar():
    """
    Inilah yang membuat `create_all` gagal SELURUHNYA.

    Penolakannya total: satu tautan salah ketik berarti tidak satu tabel pun
    dibuat. Dan karena produksi sudah terlanjur punya tabelnya, kekeliruan ini
    tidak menimbulkan gejala apa pun sampai hari skema itu benar-benar perlu
    dibangun ulang.
    """
    metadata, _ = _muat_semua_model()
    terdaftar = set(metadata.tables)

    rusak = []
    for tabel in metadata.tables.values():
        for fk in tabel.foreign_keys:
            tujuan = fk._table_key()
            if tujuan not in terdaftar:
                rusak.append(f"{tabel.name}.{fk.parent.name} -> {tujuan}")

    assert not rusak, (
        "foreign key menunjuk tabel yang tidak terdaftar; `create_all` akan "
        "menolak membangun SELURUH skema:\n  " + "\n  ".join(sorted(set(rusak)))
    )


def test_skema_dapat_disusun_menjadi_ddl():
    """
    Bukan hanya tautannya yang sah — DDL-nya harus benar-benar dapat disusun.

    `create_all` menyusun `CREATE TABLE` untuk tiap tabel sebelum
    mengirimkannya. Tipe kolom yang tidak dapat diterjemahkan ke dialek MySQL
    gagal di tahap ini, sebelum satu byte pun sampai ke basis data — dan
    gagalnya sama totalnya.
    """
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.dialects import mysql

    metadata, _ = _muat_semua_model()

    gagal = []
    for tabel in metadata.sorted_tables:
        try:
            str(CreateTable(tabel).compile(dialect=mysql.dialect()))
        except Exception as e:  # noqa: BLE001
            gagal.append(f"{tabel.name}: {e}")

    assert not gagal, "DDL tidak dapat disusun:\n  " + "\n  ".join(gagal)


def test_startup_create_tables_menyebut_setiap_berkas_model():
    """
    `create_tables.py` mengimpor modelnya SATU PER SATU.

    Model yang tidak disebut di sana tidak ikut terdaftar pada metadata saat
    skrip itu dijalankan, sehingga tabelnya tidak pernah dibuat — dan
    kekeliruannya baru terlihat ketika endpoint yang memakainya menjawab
    "table doesn't exist".
    """
    isi = open(
        os.path.join(AKAR, "startup", "create_tables.py"), encoding="utf-8"
    ).read()

    # `balance` dan `mutation` adalah VIEW, dibuat lewat SQL, bukan create_all.
    KECUALI = {"balance_model", "mutation_model"}

    hilang = []
    for berkas in sorted(glob.glob(os.path.join(AKAR, "models", "*_model.py"))):
        nama = os.path.basename(berkas)[:-3]
        if nama in KECUALI:
            continue
        # Berkas yang tidak mendefinisikan tabel apa pun tidak perlu disebut.
        # Sebagian berkas `*_model.py` hanya memuat skema Pydantic atau kueri
        # mentah (auth, dashboard) — menuntutnya di-import di sana hanya akan
        # membuat uji ini menuduh sesuatu yang benar.
        if "= Table(" not in open(berkas, encoding="utf-8").read():
            continue
        if f"models.{nama}" not in isi:
            hilang.append(nama)

    assert not hilang, (
        "berkas model tidak disebut di startup/create_tables.py, sehingga "
        "tabelnya tidak akan pernah dibuat:\n  " + "\n  ".join(hilang)
    )
