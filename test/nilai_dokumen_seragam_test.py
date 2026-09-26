"""
Nilai satu dokumen harus SAMA di setiap layar yang menyebutkannya.

Kelas kegagalan yang paling mahal di repo ini bukan rumus yang salah, melainkan
rumus yang ditulis ULANG di beberapa tempat dengan suku yang berbeda. Angkanya
masing-masing tampak masuk akal, jadi tidak ada yang curiga — sampai dua layar
menjawab berbeda atas dokumen yang sama, dan tidak ada cara menentukan mana
yang benar tanpa membongkar keduanya.

Sudah terjadi tiga kali dalam satu pekan:

  * status lunas pembelian — empat salinan, tiga hasil; dokumen lunas tercatat
    belum dibayar;
  * utang usaha — satu salinan tanpa potongan PPh; pembelian lunas menua
    selamanya di ember 90+ hari;
  * laporan pemasok — satu salinan tanpa `otherValue`; total yang ditagihkan
    lebih kecil daripada di halaman pembeliannya sendiri.

Uji di bawah memeriksa SUMBER, bukan menjalankan kuerinya: yang dijaga adalah
suku-suku rumusnya, dan yang menghilangkannya tidak akan pernah tampak sebagai
galat pada saat dijalankan.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _isi(jalur: str) -> str:
    return open(os.path.join(AKAR, jalur), encoding="utf-8").read()


def _blok(jalur: str, nama: str) -> str:
    """
    Badan satu fungsi, sampai yang berikutnya pada tingkat yang sama.

    Batas akhirnya dicari pada DUA bentuk: metode di dalam kelas (ditandai
    `@staticmethod`) dan fungsi tingkat modul. Tanpa yang kedua, potongan
    untuk fungsi di `models/` terbentang sampai ujung berkas — dan sebuah
    suku yang kebetulan muncul di bawahnya membuat uji ini lulus atas
    sesuatu yang tidak diperiksanya.
    """
    s = _isi(jalur)
    i = s.index(f"def {nama}(")
    batas = [
        j
        for j in (
            s.find("\n    @staticmethod", i),
            s.find("\ndef ", i + 1),
            s.find("\n\n\n", i),
        )
        if j != -1
    ]
    return s[i:] if not batas else s[i : min(batas)]


# ----------------------------------------------------------------------
# Pembelian: yang masih harus DITRANSFER ke pemasok
# ----------------------------------------------------------------------

#: Rumus SQL-nya kini punya SATU rumah.
#:
#: Ketiga kueri yang dulu menulisnya sendiri sekarang memanggil
#: `nilai_pembelian_sql()` di `models/purchase_model.py`. Uji di bawah karena
#: itu tidak lagi mencari suku-sukunya di masing-masing kueri — ia menuntut
#: bahwa tidak satu pun dari mereka menyusunnya sendiri lagi, dan memeriksa
#: suku-sukunya sekali di tempat rumusnya berada.
#:
#: Perhatikan bedanya: yang dulu dijaga "apakah semuanya menyebut PPh", yang
#: kini dijaga "apakah masih ada yang punya rumus sendiri". Yang kedua lebih
#: kuat — salinan yang sukunya kebetulan lengkap tetap bisa berselisih pada
#: hal lain, dan memang begitulah `otherValue` tanpa COALESCE lolos selama
#: ini.
PENYEBUT_NILAI_PEMBELIAN = (
    "repository/purchase_repository.py",
    "repository/finance_status_repository.py",
)


def test_utang_usaha_memotong_pph():
    """
    Yang tersisa pada utang usaha adalah yang masih harus dibayarkan KEPADA
    PEMASOK, dan PPh tidak pernah sampai ke pemasok — ia disetorkan ke kas
    negara.

    Tanpa memotongnya, pembelian yang sudah dibayar penuh tetap menyisakan
    "utang" sebesar PPh-nya, selamanya, dan ikut menua di ember 90+ hari.
    """
    b = _blok("repository/finance_status_repository.py", "utang_usaha")
    assert "nilai_pembelian_sql" in b, (
        "utang usaha tidak memakai penyebut bersama; rumusnya disalin lagi"
    )
    rumus = _blok("models/purchase_model.py", "nilai_pembelian_sql")
    assert "pphPercentage" in rumus, (
        "penyebut nilai pembelian tidak memotong PPh; pembelian lunas tetap "
        "tampil sebagai utang sebesar PPh-nya"
    )


def test_utang_usaha_menyertakan_other_value():
    b = _blok("repository/finance_status_repository.py", "utang_usaha")
    assert "nilai_pembelian_sql" in b
    assert "otherValue" in _blok("models/purchase_model.py", "nilai_pembelian_sql")


def test_tiga_penyebut_nilai_pembelian_memakai_suku_yang_sama():
    """
    Tiga tempat menyimpulkan berapa nilai sebuah pembelian:

      * `nilai_pembelian`      -> menentukan status LUNAS (Python)
      * `belum_dibayar`        -> daftar tagihan yang belum lunas (SQL)
      * `utang_usaha`          -> ember umur utang (SQL)

    Dua yang terakhir kini memanggil `nilai_pembelian_sql()`, sehingga tidak
    mungkin lagi berselisih satu sama lain. Yang tersisa dijaga di sini:
    suku-suku pada versi SQL dan versi Python-nya tetap sama.
    """
    for jalur in PENYEBUT_NILAI_PEMBELIAN:
        isi = _isi(jalur)
        assert "nilai_pembelian_sql" in isi, (
            f"{jalur} menyusun sendiri nilai pembelian"
        )

    potongan = {
        "nilai_pembelian": _blok(
            "controllers/payment_outgoing_controller.py", "nilai_pembelian"
        ),
        "nilai_pembelian_sql": _blok(
            "models/purchase_model.py", "nilai_pembelian_sql"
        ),
    }

    for nama, b in potongan.items():
        for suku in ("dpp", "ppn", "pbbkb", "otherValue", "pphPercentage"):
            assert suku in b, f"{nama} tidak menyebut {suku}"


# ----------------------------------------------------------------------
# Pemasok: yang DITAGIHKAN
# ----------------------------------------------------------------------

def test_laporan_pemasok_menyertakan_other_value():
    """
    `otherValue` bagian dari nilai faktur — ongkos angkut, bongkar muat.
    Tertinggal di sini saja, total yang ditagihkan pemasok pada laporannya
    lebih kecil daripada di halaman pembeliannya sendiri.
    """
    b = _blok("repository/supplier_repository.py", "laporan")
    assert "otherValue" in b


# ----------------------------------------------------------------------
# Slip gaji: satu rumus, bukan salinan mentah
# ----------------------------------------------------------------------

def test_nilai_slip_tidak_disalin_mentah():
    """
    Salinan mentahnya menjumlahkan kolom LANGSUNG, tanpa `or 0`: satu kolom
    NULL — tunjangan yang belum diisi, `taxAmount` pada slip lama — membuat
    penjumlahannya melempar TypeError, dan persetujuan pembayarannya gagal
    tanpa menyebut sebabnya.

    `nilai_slip` sudah menanganinya; yang tersisa hanya memastikan tidak ada
    yang menghitungnya sendiri lagi.
    """
    s = _isi("controllers/payment_outgoing_controller.py")
    salinan = re.findall(r'salarySlip\["basicSalary"\]\s*\+', s)
    assert not salinan, (
        f"masih ada {len(salinan)} salinan mentah rumus nilai slip; "
        "pakai `nilai_slip()`"
    )


def test_nilai_slip_dipakai_seluruh_jalur():
    """
    Empat kemunculan: satu definisi, tiga pemakaian — persetujuan tunggal,
    persetujuan massal, dan penyelarasan status lunas.
    """
    s = _isi("controllers/payment_outgoing_controller.py")
    assert s.count("nilai_slip(") >= 4


def test_nilai_slip_tahan_kolom_kosong():
    b = _blok("controllers/payment_outgoing_controller.py", "nilai_slip")
    assert b.count("or 0") >= 6, (
        "nilai_slip harus menahan kolom NULL pada setiap sukunya"
    )
