"""
Tender: nomor penawaran, keterangan berkategori, dan penutupan tanpa pemenang.

Tiga hal yang ditambahkan bersamaan, dan tiga kelas kegagalan yang berbeda:

  * `noteList` BUKAN kolom `tender_quotes`. Meneruskannya apa adanya ke INSERT
    melempar "Unconsumed column names" — yang di repo ini ditelan
    `except Exception` dan keluar sebagai 500 tanpa menyebut sebabnya. Persis
    bentuk kegagalan yang membuat `PUT /income/{id}` rusak berbulan-bulan.

  * Kategori yang diketik bebas menghasilkan "Pembayaran" dan "pembayaran"
    sebagai dua baris terpisah pada tabel yang seluruh gunanya menyejajarkan
    hal yang sama. Karena itu daftarnya tertutup, dan ketertutupannya dijaga.

  * Penutupan tanpa pemenang TIDAK boleh menuntut tiga penawaran. Tender yang
    ditutup tanpa pemenang justru kerap tender yang penawarannya tidak pernah
    cukup — menuntut tiga memaksanya menggantung selamanya, tampil sebagai
    pekerjaan yang belum selesai padahal keputusannya sudah diambil.
"""

import ast
import inspect
import os
import textwrap

import pytest
from pydantic import ValidationError

from models.tender_model import KATEGORI_KETERANGAN, tender_quote_notes_table
from schemas.tender_schema import (
    TenderQuoteCreate,
    TenderQuoteNoteBase,
    TenderQuoteUpdate,
    TenderTutup,
)

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _isi(jalur: str) -> str:
    return open(os.path.join(AKAR, jalur), encoding="utf-8").read()


# ----------------------------------------------------------------------
# Kategori tertutup
# ----------------------------------------------------------------------


def test_kategori_di_luar_daftar_ditolak():
    for sah in KATEGORI_KETERANGAN:
        TenderQuoteNoteBase(category=sah, content="x")

    for asing in ("bbm", "Pembayaran", "PEMBAYARAN", "", "garansi"):
        with pytest.raises(ValidationError):
            TenderQuoteNoteBase(category=asing, content="x")


def test_keterangan_kosong_ditolak_skemanya():
    """Keterangan tanpa isi tidak punya arti pada tabel perbandingan."""
    with pytest.raises(ValidationError):
        TenderQuoteNoteBase(category="teknis", content="")


def test_daftar_kategori_sama_di_model_dan_skema():
    """
    Satu daftar, bukan dua.

    Skema mengimpor daftarnya dari model — diperiksa di sini supaya salinan
    kedua tidak diam-diam muncul kembali dan berselisih.
    """
    s = _isi("schemas/tender_schema.py")
    assert "from models.tender_model import KATEGORI_KETERANGAN" in s
    assert '"pembayaran"' not in s.split("KATEGORI_KETERANGAN")[-1][:2000], (
        "daftar kategori disalin ulang di skema"
    )


# ----------------------------------------------------------------------
# `noteList` tidak boleh bocor ke kolom tabel
# ----------------------------------------------------------------------


def _nama_kolom_quotes() -> set:
    from models.tender_model import tender_quotes_table

    return {c.name for c in tender_quotes_table.columns}


def test_notelist_dikeluarkan_sebelum_baris_penawaran_ditulis():
    """
    Controller wajib `pop("noteList")` sebelum muatannya sampai ke repository.

    Diperiksa lewat AST, bukan dengan menjalankan INSERT: kegagalannya baru
    muncul saat pernyataan SQL-nya DISUSUN, dan di jalur itu ia sudah
    tertelan `except Exception`.
    """
    assert "noteList" not in _nama_kolom_quotes(), (
        "`noteList` ternyata kolom tabel; uji ini perlu ditinjau ulang"
    )

    pohon = ast.parse(_isi("controllers/tender_controller.py"))
    for nama in ("tambah_penawaran", "ubah_penawaran"):
        fungsi = next(
            n
            for n in ast.walk(pohon)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == nama
        )
        sumber = ast.get_source_segment(
            _isi("controllers/tender_controller.py"), fungsi
        )
        assert 'pop("noteList"' in sumber, (
            f"`{nama}` tidak mengeluarkan `noteList` dari muatan; "
            "INSERT-nya akan melempar Unconsumed column names, dan galat itu "
            "keluar sebagai 500 tanpa menyebut sebabnya"
        )


def test_quotation_number_disebut_di_base_dan_update():
    """
    Skema `*Update` di berkas ini tidak mewarisi `*Base`.

    Kolom baru karena itu harus disebut DUA kali — Pydantic membuang bidang
    yang tidak dikenalnya tanpa galat, sehingga muatan yang benar tersimpan
    sebagai NULL dan jawabannya tetap sukses.
    """
    assert "quotationNumber" in TenderQuoteCreate.model_fields
    assert "quotationNumber" in TenderQuoteUpdate.model_fields
    assert "noteList" in TenderQuoteCreate.model_fields
    assert "noteList" in TenderQuoteUpdate.model_fields


# ----------------------------------------------------------------------
# Penutupan tanpa pemenang
# ----------------------------------------------------------------------


def test_penutupan_menuntut_alasan_tertulis():
    with pytest.raises(ValidationError):
        TenderTutup(reason="")
    with pytest.raises(ValidationError):
        TenderTutup(reason="mahal")  # di bawah 10 aksara
    TenderTutup(reason="Seluruh penawaran melampaui pagu proyek.")


def test_penutupan_tidak_menuntut_tiga_penawaran():
    """
    `MINIMAL_PENAWARAN` tidak boleh disebut di cabang penutupan.

    Tender yang ditutup tanpa pemenang kerap justru yang penawarannya tidak
    pernah cukup; menuntut tiga memaksanya menggantung selamanya.
    """
    from controllers.tender_controller import TenderController

    sumber = inspect.getsource(TenderController.tutup_tanpa_pemenang)

    # Keterangannya DIBUANG lebih dulu; ia memang menyebut
    # `MINIMAL_PENAWARAN` untuk menerangkan mengapa aturan itu tidak berlaku,
    # dan memeriksa teks bersama keterangannya akan menghukum penjelasan yang
    # justru diperlukan.
    pohon = ast.parse(textwrap.dedent(sumber))
    fungsi = pohon.body[0]
    if (
        fungsi.body
        and isinstance(fungsi.body[0], ast.Expr)
        and isinstance(fungsi.body[0].value, ast.Constant)
    ):
        fungsi.body = fungsi.body[1:]
    kode = ast.unparse(fungsi)

    assert "MINIMAL_PENAWARAN" not in kode, (
        "penutupan tanpa pemenang menuntut jumlah penawaran minimum"
    )
    # Yang TETAP dituntut: tendernya belum selesai dan belum dibatalkan.
    assert "'selesai'" in kode and "'batal'" in kode


def test_penutupan_tidak_menambah_nilai_status_baru():
    """
    Tender yang ditutup tanpa pemenang tetap berstatus `selesai`.

    Menambah nilai status baru berarti setiap penyaring, chip, dan laporan
    yang mengenal empat nilai harus ikut diubah — dan yang terlewat akan
    diam-diam menyembunyikan tendernya dari layar.
    """
    from schemas.tender_schema import STATUS_TENDER

    assert STATUS_TENDER == {"draft", "berjalan", "selesai", "batal"}

    sumber = _isi("repository/tender_repository.py")
    i = sumber.index("async def tutup_tanpa_pemenang")
    cabang = sumber[i : i + 2000]
    assert 'status="selesai"' in cabang
    assert "winnerQuoteID=None" in cabang, (
        "pemenangnya harus tetap kosong — itulah yang membedakannya dari "
        "tender yang pemenangnya ditetapkan"
    )


# ----------------------------------------------------------------------
# Jalan mundur untuk penawaran lama
# ----------------------------------------------------------------------


def test_keterangan_lama_tetap_terbaca():
    """
    Penawaran yang tersimpan sebelum kategori ada tidak boleh kehilangan
    keterangannya.

    Teks lamanya ada di `tender_quotes.notes`, dan tanpa jalan mundur ia
    menghilang dari layar seolah tidak pernah ditulis.
    """
    sumber = _isi("repository/tender_repository.py")
    assert "async def _keterangan" in sumber
    i = sumber.index("async def _keterangan")
    blok = sumber[i : i + 2500]
    assert 'quote.get("notes")' in blok, (
        "tidak ada jalan mundur ke kolom keterangan lama"
    )
    assert '"lainnya"' in blok


def test_menyimpan_keterangan_mengosongkan_kolom_lama():
    """
    Dua sumber tidak boleh terisi sekaligus.

    Bila kolom lama dibiarkan terisi setelah keterangan berkategori
    tersimpan, satu penawaran menampilkan keterangannya DUA KALI di tabel
    perbandingan.
    """
    sumber = _isi("repository/tender_repository.py")
    i = sumber.index("async def _tulis_keterangan")
    blok = sumber[i : i + 2500]
    assert "notes=None" in blok, (
        "kolom keterangan lama tidak dikosongkan; isinya akan tampil dua kali"
    )


def test_tabel_keterangan_punya_kolom_yang_diperlukan():
    kolom = {c.name for c in tender_quote_notes_table.columns}
    assert kolom == {"id", "quoteID", "category", "content", "sortOrder"}
