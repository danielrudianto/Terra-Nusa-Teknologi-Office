"""
Nilai tagihan sebuah pembelian: satu rumus, satu tempat.

Kegagalan yang ditutup di sini
------------------------------

Pembelian yang SUDAH dibayar penuh tetap bertanda "belum dibayar", dan tombol
"selaraskan status lunas" tidak memperbaikinya — justru mengulang kesalahan
yang sama setiap kali ditekan.

Sebabnya bukan angka yang salah dihitung, melainkan rumus yang ditulis EMPAT
kali di satu berkas dengan TIGA hasil berbeda:

  * saat pembayaran disetujui      -> DPP + PPN + PBBKB + otherValue - PPh
  * saat persetujuan massal        -> sama, lengkap
  * saat memeriksa sisa tagihan    -> tanpa otherValue, tanpa PPh
  * saat menyelaraskan status      -> tanpa otherValue, tanpa PPh

Urutannya yang mematikan: persetujuan menandai lunas dengan rumus yang benar,
lalu `selaraskan_status_lunas` menghitung ulang dengan rumus yang kekurangan
potongan PPh, mendapati "kurang bayar" sebesar PPh-nya, dan MENCABUT tanda
lunas yang baru saja dipasang. Tanpa galat, tanpa catatan.

PPh itu memang tidak pernah sampai ke pemasok — ia dipotong dan disetorkan ke
kas negara. Menuntutnya sebagai kekurangan bayar berarti menunggu uang yang
tidak akan pernah ditransfer siapa pun.

Dua kejadian sungguhan:

    DPP 280.080.000 + PPN 11% - PPh 2,65%  -> dibayar 303.466.680
    DPP  40.500.000 + PPN 11% - PPh 2%     -> dibayar  44.145.000

Keduanya lunas, keduanya tercatat belum dibayar.

Yang dijaga uji ini bukan hanya angkanya, melainkan bahwa rumusnya tinggal
SATU — sebab dua salinan yang hari ini setuju akan berselisih pada perubahan
berikutnya, dan selisihnya berupa dokumen yang ditandai lunas oleh satu rumus
lalu tidak pernah dapat dicabut oleh yang lain.
"""

import ast
import os
import re

import pytest

from controllers.payment_outgoing_controller import nilai_pembelian

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERKAS = os.path.join(AKAR, "controllers", "payment_outgoing_controller.py")


class _Baris(dict):
    """
    Menyerupai `databases.Record`: dibaca lewat kunci, bukan `.get()`.

    Sengaja BUKAN `dict` biasa dalam penggunaannya — baris sungguhan tidak
    punya `.get()`, dan rumus yang diam-diam mengandalkannya akan lolos uji
    lalu gagal di produksi.
    """


# ----------------------------------------------------------------------
# Angkanya
# ----------------------------------------------------------------------

def test_pph_dipotong_dari_nilai_tagihan():
    """Kejadian pertama: 280.080.000, PPN 11%, PPh 2,65%."""
    nilai = nilai_pembelian(
        _Baris(
            dpp=280_080_000,
            ppn=11,
            pbbkb=0,
            otherValue=0,
            pphPercentage=2.65,
        )
    )
    assert nilai == 303_466_680, (
        "PPh harus dipotong; ia disetor ke kas negara, bukan ke pemasok"
    )


def test_kejadian_kedua_juga_cocok():
    """Kejadian kedua: 40.500.000, PPN 11%, PPh 2%."""
    nilai = nilai_pembelian(
        _Baris(
            dpp=40_500_000,
            ppn=11,
            pbbkb=0,
            otherValue=0,
            pphPercentage=2,
        )
    )
    assert nilai == 44_145_000


def test_other_value_ikut_ditambahkan():
    """
    `otherValue` hilang dari dua salinan rumus yang lama. Arahnya berlawanan
    dengan PPh — ia MENAMBAH tagihan — sehingga kekeliruannya menandai lunas
    dokumen yang sebenarnya masih kurang bayar.
    """
    tanpa = nilai_pembelian(
        _Baris(dpp=10_000_000, ppn=0, pbbkb=0, otherValue=0, pphPercentage=0)
    )
    dengan = nilai_pembelian(
        _Baris(dpp=10_000_000, ppn=0, pbbkb=0, otherValue=250_000, pphPercentage=0)
    )
    assert dengan - tanpa == 250_000


def test_pbbkb_ikut_ditambahkan():
    nilai = nilai_pembelian(
        _Baris(dpp=1_000_000, ppn=0, pbbkb=75_000, otherValue=0, pphPercentage=0)
    )
    assert nilai == 1_075_000


def test_kolom_kosong_tidak_menjatuhkan_perhitungan():
    """
    Baris lama boleh punya `otherValue` atau `pphPercentage` kosong. Rumus
    yang jatuh pada `None` membuat SELURUH penyelarasan status berhenti,
    bukan cuma satu dokumen.
    """
    nilai = nilai_pembelian(
        _Baris(
            dpp=1_000_000,
            ppn=None,
            pbbkb=None,
            otherValue=None,
            pphPercentage=None,
        )
    )
    assert nilai == 1_000_000


def test_kolom_yang_tidak_ada_diperlakukan_nol():
    """
    Sebagian kueri tidak memilih seluruh kolom. Yang tidak terpilih tidak
    boleh menjatuhkan perhitungannya — cukup dianggap nol.
    """
    nilai = nilai_pembelian(_Baris(dpp=2_000_000, ppn=11))
    assert nilai == 2_220_000


# ----------------------------------------------------------------------
# Yang sebenarnya dijaga: rumusnya tinggal satu
# ----------------------------------------------------------------------

def test_rumus_pembelian_tidak_ditulis_ulang_di_tempat_lain():
    """
    Inilah penjaga sesungguhnya.

    Angka yang benar hari ini tidak menjamin apa pun bila rumusnya masih
    tersebar. Yang membuat bug ini hidup berbulan-bulan bukan kesalahan
    hitung, melainkan EMPAT salinan yang boleh berbeda pendapat tanpa ada
    yang memberitahu.

    Uji ini menolak salinan baru: perkalian `ppn` dengan `dpp` hanya boleh
    muncul di dalam `nilai_pembelian`.
    """
    isi = open(BERKAS, encoding="utf-8").read()
    pohon = ast.parse(isi)

    fungsi = next(
        (
            n
            for n in ast.walk(pohon)
            if isinstance(n, ast.FunctionDef) and n.name == "nilai_pembelian"
        ),
        None,
    )
    assert fungsi is not None, "nilai_pembelian hilang dari controller"

    baris_fungsi = set(range(fungsi.lineno, (fungsi.end_lineno or fungsi.lineno) + 1))

    pola = re.compile(r'(\["ppn"\]|\.ppn)\s*\*')
    pelanggar = [
        (i, b.strip())
        for i, b in enumerate(isi.splitlines(), start=1)
        if pola.search(b) and i not in baris_fungsi
    ]

    assert not pelanggar, (
        "rumus nilai pembelian ditulis ulang di luar `nilai_pembelian`; "
        "salinan yang berselisih persis itulah yang membuat dokumen lunas "
        "ditandai belum dibayar:\n  "
        + "\n  ".join(f"baris {i}: {b}" for i, b in pelanggar)
    )


def test_seluruh_jalur_status_lunas_memakai_rumus_yang_sama():
    """
    Empat jalur menyimpulkan status lunas sebuah pembelian: persetujuan
    tunggal, persetujuan massal, pemeriksaan sisa tagihan, dan penyelarasan.
    Semuanya harus memanggil fungsi yang sama.

    Cukup satu yang tidak, dan yang tiga lainnya kembali dapat dibantah —
    persis seperti sebelum perbaikan ini.
    """
    isi = open(BERKAS, encoding="utf-8").read()
    jumlah = isi.count("nilai_pembelian(")

    # 1 definisi + minimal 4 pemakaian.
    assert jumlah >= 5, (
        f"`nilai_pembelian` hanya muncul {jumlah} kali; ada jalur status "
        "lunas yang masih menghitung sendiri"
    )
