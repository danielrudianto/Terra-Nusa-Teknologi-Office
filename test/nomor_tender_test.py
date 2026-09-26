"""
Nomor dokumen tender: `T-AKN-001-IX-2026`.

SEBELUMNYA nomornya sebuah INT yang naik terus — "3". Nomor seperti itu tidak
dapat dirujuk di luar sistem: di WhatsApp, di berkas cetak, di surat ke
pemasok, "tender 3" tidak menyebut tahun dan tidak menyebut perusahaan, dan
tahun depan akan ada "tender 3" yang lain.

DUA HAL YANG PALING MUDAH SALAH DI SINI, dan keduanya tidak menghasilkan galat:

  * Urutannya diambil dari SELURUH tabel, bukan per tahun. Nomornya tetap
    tampil rapi — cuma tidak pernah mengulang, sehingga bagian tahunnya jadi
    hiasan dan angkanya memanjang tanpa alasan.

  * Bulannya diambil dari HARI INI, bukan dari tanggal tendernya. Tender yang
    dicatat 2 Oktober untuk dokumen bertanggal 28 September akan bernomor
    `...-X-...`. Tidak ada yang menyadarinya sampai ada yang mencocokkan
    nomor dengan tanggal di berkasnya.
"""

import os
import re
from datetime import date

from repository.tender_repository import (
    AWALAN_TENDER,
    BULAN_ROMAWI,
    format_nomor_tender,
)

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(AKAR, "repository", "tender_repository.py")
SQL = os.path.join(AKAR, "sql", "tender-nomor-dokumen.sql")


def _blok(berkas: str, nama: str) -> str:
    """Badan sebuah fungsi, TANPA komentar dan TANPA docstring.

    Docstring harus ikut dibuang, bukan cuma baris `#`. Docstring
    `nomor_berikutnya` menjelaskan panjang lebar KENAPA `isDelete` tidak
    disaring — dan uji yang mencari kata "isDelete" di badan fungsi menjadi
    merah justru karena penjelasan bahwa hal itu memang tidak dilakukan.

    Kelas kesalahan yang sama pernah membuat uji migrasi mobilisasi HIJAU
    padahal saringannya sudah dicabut: yang terbaca prosanya, bukan kodenya.
    Di sini arahnya kebetulan terbalik, tetapi sebabnya persis sama.
    """
    s = open(berkas, encoding="utf-8").read()
    i = s.index(f"async def {nama}(")
    j = s.find("async def ", i + 10)
    blok = s[i:] if j == -1 else s[i:j]
    blok = re.sub(r'"""[\s\S]*?"""', "", blok)
    return "\n".join(
        b for b in blok.splitlines() if not b.lstrip().startswith("#")
    )


# ----------------------------------------------------------------------
# Bentuk nomornya
# ----------------------------------------------------------------------


def test_bentuknya_persis():
    assert format_nomor_tender(1, date(2026, 9, 15)) == "T-AKN-001-IX-2026"
    assert format_nomor_tender(7, date(2026, 1, 2)) == "T-AKN-007-I-2026"
    assert format_nomor_tender(123, date(2027, 12, 31)) == "T-AKN-123-XII-2027"


def test_nol_di_depan_adalah_MINIMUM_bukan_batas():
    """
    Tender ke-1000 tidak boleh terpotong menjadi `000`.

    `:03d` menambah nol sampai tiga digit; ia tidak memotong. Kalau suatu saat
    diganti menjadi pemotongan, dua tender akan bernomor sama dalam satu tahun
    dan indeks uniknya baru menolaknya di produksi.
    """
    assert format_nomor_tender(1000, date(2026, 4, 1)) == "T-AKN-1000-IV-2026"


def test_seluruh_dua_belas_bulan_romawi():
    romawi = [format_nomor_tender(1, date(2026, b, 1)).split("-")[3] for b in range(1, 13)]
    assert romawi == [
        "I", "II", "III", "IV", "V", "VI",
        "VII", "VIII", "IX", "X", "XI", "XII",
    ]
    assert BULAN_ROMAWI[0] is None, "indeks 0 harus kosong; bulan mulai dari 1"


def test_awalannya_satu_tempat():
    """
    Nomor yang disusun di dua tempat akan berbeda pada perkara kecil — nol di
    depan, pemisah — dan perbedaannya baru ketahuan setelah beredar.
    """
    assert format_nomor_tender(1, date(2026, 9, 1)).startswith(AWALAN_TENDER + "-")


# ----------------------------------------------------------------------
# Urutannya
# ----------------------------------------------------------------------


def test_urutan_dihitung_PER_TAHUN():
    b = _blok(REPO, "nomor_berikutnya")
    assert "func.year" in b, (
        "urutannya tidak disaring per tahun — bagian tahun pada nomornya jadi "
        "hiasan dan angkanya memanjang tanpa alasan"
    )
    assert "func.max" in b and "func.count" not in b


def test_yang_terhapus_TETAP_terhitung():
    """
    Aturan ini sudah ada sebelum format barunya, dan tetap berlaku.

    Kalau yang terhapus dilewati, tender berikutnya mewarisi nomor milik
    tender yang pernah ada — dan rujukan lama ke nomor itu diam-diam menunjuk
    dokumen yang berbeda.
    """
    b = _blok(REPO, "nomor_berikutnya")
    assert "isDelete" not in b, (
        "`nomor_berikutnya` menyaring `isDelete` — nomornya akan dipakai ulang"
    )


def test_nomor_dari_tanggal_tender_bukan_hari_ini():
    b = _blok(REPO, "buat")
    assert 'nilai.get("date")' in b, (
        "tanggalnya tidak diambil dari tendernya — tender yang dicatat "
        "terlambat akan bernomor bulan yang salah"
    )
    assert "documentNumber=nomor_dokumen" in b


# ----------------------------------------------------------------------
# SQL pemasangannya
# ----------------------------------------------------------------------


def test_sql_mengisi_termasuk_yang_terhapus():
    """
    Baris terhapus HARUS ikut dinomori saat pengisian ulang.

    Dilewati, urutannya jadi rapat — dan tender berikutnya akan memakai nomor
    yang sebenarnya sudah pernah terbit.
    """
    s = open(SQL, encoding="utf-8").read()
    isi = s[s.index("UPDATE tenders"):s.index("-- 3.")]
    isi_tanpa_komentar = "\n".join(
        b for b in isi.splitlines() if not b.lstrip().startswith("--")
    )
    assert "isDelete" not in isi_tanpa_komentar, (
        "pengisian ulang menyaring `isDelete` — nomor akan dipakai ulang"
    )
    assert "PARTITION BY YEAR(date)" in isi_tanpa_komentar
    assert "ORDER BY date, id" in isi_tanpa_komentar


def test_sql_memasang_indeks_unik():
    s = open(SQL, encoding="utf-8").read()
    assert re.search(r"ADD UNIQUE INDEX\s+\w+\s*\(documentNumber\)", s), (
        "tanpa indeks unik, dua dokumen bernomor sama tidak akan tertahan"
    )
