"""
Rumus nilai dokumen di dalam KUERI — satu sumber, dan NULL-nya dijinakkan.

`nilai_dokumen_seragam_test` sudah menjaga suku-suku rumusnya. Yang tidak
dijaganya, dan yang ternyata jauh lebih mahal, adalah bagaimana rumus itu
berperilaku terhadap kolom yang boleh kosong.

`purchases.otherValue` boleh NULL, dan kebanyakan pembelian memang
menyimpannya NULL — ongkos angkut dan bongkar muat hanya ada pada sebagian
dokumen. Di SQL, apa pun yang ditambahkan pada NULL menjadi NULL; `NULL > 5`
bukan benar dan bukan salah melainkan UNKNOWN; dan baris yang syaratnya
UNKNOWN TIDAK IKUT TERPILIH.

Akibatnya bukan angka yang keliru, melainkan **baris yang lenyap**: pembelian
yang belum dibayar sepeser pun tidak muncul di daftar "belum dibayar" maupun
di rekap utang bulanan. Tidak ada galat, tidak ada baris kosong, tidak ada
selisih yang bisa dihitung siapa pun. Yang menagihnya hanya tidak pernah
melihatnya lagi — sementara penentu status lunas, yang memakai `float(x or 0)`,
tetap menganggap dokumen itu berutang penuh.

Uji di bawah MENJALANKAN kuerinya terhadap basis data sungguhan, bukan
membaca sumbernya: kegagalan bentuk ini tidak dapat dilihat dari teks rumus,
hanya dari barisnya yang tidak kembali.
"""

import os
import re

import pytest
from sqlalchemy import select

from models.purchase_model import nilai_pembelian_sql, purchases_table
from models.sales_invoice_model import (
    nilai_faktur_sql,
    sales_invoice_tables,
    terbayar_faktur_sql,
)

#: Hanya dua uji terakhir yang butuh basis data.
#:
#: Pemeriksaan BENTUK rumusnya harus tetap berjalan di mesin mana pun —
#: itulah yang menangkap kolom telanjang yang boleh NULL, dan itulah yang
#: dijalankan `deploy.sh`. Menandai seluruh modulnya membuat penjagaannya
#: ikut dilewati di tempat yang paling perlu.
butuh_basis = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="butuh TEST_DATABASE_URL; uji ini membaca basis data",
)


# ----------------------------------------------------------------------
# Bentuk rumusnya — dapat diperiksa tanpa basis data
# ----------------------------------------------------------------------


def test_setiap_kolom_yang_boleh_kosong_dibungkus_coalesce():
    """
    Tidak boleh ada kolom telanjang yang boleh NULL di dalam rumusnya.

    Diperiksa dari SQL yang tersusun, bukan dari kode sumbernya: yang
    menentukan bukan bagaimana rumusnya ditulis melainkan bagaimana ia
    dikompilasi.
    """
    sql = str(nilai_pembelian_sql())
    for kolom in ("otherValue", "pbbkb", "ppn", "pphPercentage"):
        telanjang = f'purchases."{kolom}"' if kolom[0].isupper() or any(
            c.isupper() for c in kolom
        ) else f"purchases.{kolom}"
        assert f"coalesce({telanjang}" in sql, (
            f"`{kolom}` tidak dibungkus COALESCE; satu baris NULL "
            f"menghapus seluruh pembelian dari daftar. SQL: {sql}"
        )

    sql_faktur = str(nilai_faktur_sql())
    for kolom in ("ppn", "bpjs"):
        assert f"coalesce(sales_invoices.{kolom}" in sql_faktur, (
            f"`{kolom}` tidak dibungkus COALESCE. SQL: {sql_faktur}"
        )
    assert 'coalesce(sales_invoices."pphPercentage"' in sql_faktur


def test_pembayaran_masuk_menyaring_yang_dibatalkan():
    """
    Pembayaran yang dibatalkan tidak boleh ikut menutup piutang.

    Keempat subkueri yang menjumlahkannya dulu tidak menyaring `isDelete`
    sama sekali — sehingga pembayaran yang tercatat ke faktur keliru lalu
    dihapus tetap membuat faktur itu terbaca lunas, dan faktur itu hilang
    dari umur piutang maupun rekap bulanan senilai penuh, tanpa jejak.
    """
    sql = str(terbayar_faktur_sql().element)
    assert '"isDelete"' in sql or "isDelete" in sql, (
        f"subkueri pembayaran masuk tidak menyaring isDelete: {sql}"
    )


def test_piutang_dan_daftar_faktur_memakai_rumus_yang_sama():
    """
    Nilai faktur hanya boleh berasal dari SATU tempat.

    `piutang()` dulu menilainya `DPP + PPN` saja sementara penentu lunas
    memakai `DPP + PPN − PPh − BPJS`. Dengan pembayaran yang dicatat neto,
    sisanya tidak pernah mencapai nol: setiap faktur yang sudah lunas
    meninggalkan piutang abadi sebesar PPh + BPJS.
    """
    akar = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for jalur in (
        "repository/finance_status_repository.py",
        "repository/sales_invoice_repository.py",
    ):
        isi = open(os.path.join(akar, jalur), encoding="utf-8").read()
        assert "nilai_faktur_sql" in isi, (
            f"{jalur} tidak memakai `nilai_faktur_sql`; rumusnya disalin lagi"
        )
        # Rumus yang disalin mentah tidak boleh tersisa.
        assert "* sales_invoice_tables.c.dpp / 100" not in isi.replace(
            "nilai_faktur_sql", ""
        ) or "def nilai_faktur_sql" in isi


def test_nilai_pembelian_sql_dipakai_di_setiap_kueri_yang_menilainya():
    akar = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for jalur in (
        "repository/purchase_repository.py",
        "repository/finance_status_repository.py",
    ):
        isi = open(os.path.join(akar, jalur), encoding="utf-8").read()
        assert "nilai_pembelian_sql" in isi, (
            f"{jalur} menyusun sendiri nilai pembelian; "
            "gunakan `nilai_pembelian_sql()`"
        )
        # Disebut sebagai KOLOM yang dipilih tidak apa-apa — yang dilarang
        # adalah menyebutnya di dalam PERHITUNGAN tanpa COALESCE, karena di
        # situlah satu NULL menelan seluruh nilainya.
        telanjang = re.findall(
            r"[+\-]\s*\n?\s*purchases_table\.c\.otherValue"
            r"|purchases_table\.c\.otherValue\s*\n?\s*[+\-]",
            isi,
        )
        assert not telanjang, (
            f"{jalur} masih menghitung dengan `otherValue` telanjang "
            f"({len(telanjang)} tempat) — itu kolom yang boleh NULL; "
            "pakai `nilai_pembelian_sql()`"
        )


# ----------------------------------------------------------------------
# Terhadap basis data sungguhan
# ----------------------------------------------------------------------


@butuh_basis
async def test_pembelian_ber_othervalue_null_tetap_terhitung(klien, bersihkan):
    """
    Pembelian dengan `otherValue` NULL harus tetap punya nilai.

    Inilah kegagalan yang sebenarnya: bukan angkanya meleset, melainkan
    kuerinya mengembalikan NULL sehingga barisnya tersaring habis.
    """
    from utils.database import database

    baris = await database.fetch_one(
        select(nilai_pembelian_sql().label("nilai")).where(
            purchases_table.c.otherValue.is_(None)
        )
    )
    if baris is None:
        pytest.skip("tidak ada pembelian ber-otherValue NULL di basis uji")

    assert baris["nilai"] is not None, (
        "nilai pembelian menjadi NULL karena `otherValue` kosong; "
        "seluruh barisnya akan lenyap dari daftar belum-dibayar"
    )


@butuh_basis
async def test_nilai_faktur_tidak_null_walau_bpjs_kosong(klien, bersihkan):
    from utils.database import database

    baris = await database.fetch_one(select(nilai_faktur_sql().label("nilai")))
    if baris is None:
        pytest.skip("tidak ada faktur penjualan di basis uji")
    assert baris["nilai"] is not None
