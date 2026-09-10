"""
Posisi PPh: dua bagian yang tidak boleh dijumlahkan, dan satu jebakan hitung.

PPh 21 (gaji) dan PPh 23/4(2) (potongan ke vendor) disetor dengan kode billing
dan formulir SPT yang berbeda, dan yang melapor mengisinya sendiri-sendiri.
Satu angka gabungan membuat satu masa tampak lunas padahal yang disetor baru
salah satunya — dan sekali dijumlahkan, tidak ada cara membacanya kembali
menjadi dua.

Jebakan hitungnya: kueri sumber PPh menghasilkan satu baris per PEMBAYARAN,
dan tiap baris membawa DPP dokumen secara UTUH. Tagihan yang dicicil tiga kali
dalam satu masa akan menghitung PPh-nya tiga kali. Angka yang dipakai
memutuskan berapa yang disetor tidak boleh bergantung pada berapa kali kasir
mencicilnya.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTRL = "controllers/tax_controller.py"
REPO = "repository/expense_repository.py"


def _blok(relatif: str, nama: str) -> str:
    """
    Badan sebuah fungsi, tanpa komentar DAN tanpa docstring.

    Keduanya dibuang karena keterangan yang MENYEBUT sesuatu bukan kode yang
    melakukannya — docstring yang berbunyi "tidak ada kompensasi antar masa"
    akan membuat uji yang mencari kata itu gagal justru ketika kodenya benar.
    """
    s = open(os.path.join(AKAR, relatif), encoding="utf-8").read()
    i = s.index(f"async def {nama}(")
    j = s.find("async def ", i + 10)
    blok = s[i:] if j == -1 else s[i:j]
    blok = re.sub(r'"""(?:.|\n)*?"""', "", blok)
    return "\n".join(
        b for b in blok.splitlines() if not b.lstrip().startswith("#")
    )


# ----------------------------------------------------------------------
# Bentuk jawabannya
# ----------------------------------------------------------------------

def test_gaji_dan_pembelian_dipisah():
    b = _blok(CTRL, "get_pph_position")
    assert '"gaji"' in b and '"pembelian"' in b, (
        "posisi PPh tidak memisahkan gaji dari pembelian"
    )


def test_keduanya_tidak_dijumlahkan_menjadi_satu_angka():
    """
    Satu total gabungan menghapus perbedaan yang justru menentukan: kode
    billing dan formulir SPT-nya berbeda.
    """
    b = _blok(CTRL, "get_pph_position")
    assert not re.search(r"terutang_gaji\s*\+\s*terutang_pembelian", b)
    assert not re.search(r"terutang_pembelian\s*\+\s*terutang_gaji", b)


def test_tiap_bagian_menyebut_terutang_setoran_dan_sisanya():
    b = _blok(CTRL, "get_pph_position")
    for kunci in ('"terutang"', '"setoran"', '"setoranDibayar"', '"sisa"', '"keadaan"'):
        assert kunci in b, f"bagian posisi tidak menyebut {kunci}"


def test_kesimpulan_keadaan_diambil_dari_utils_pajak():
    """
    Bila tiap layar menyimpulkan sendiri apakah satu masa sudah selesai, dua
    layar akan menjawab berbeda atas angka yang sama.
    """
    b = _blok(CTRL, "get_pph_position")
    assert "status_setoran(" in b


# ----------------------------------------------------------------------
# Jebakan hitung
# ----------------------------------------------------------------------

def test_satu_dokumen_dihitung_sekali_walaupun_dicicil():
    b = _blok(CTRL, "get_pph_position")
    assert "terlihat" in b and "continue" in b, (
        "tidak ada penyaringan dokumen berulang; tagihan yang dicicil tiga "
        "kali akan menghitung PPh-nya tiga kali"
    )
    # Kuncinya harus menyertakan SUMBER: id pembelian dan id beban berjalan
    # di urutan yang terpisah, sehingga id yang sama dapat muncul di keduanya.
    assert '("purchase", r.get("id"))' in b
    assert '("expense", r.get("id"))' in b


def test_pph_dihitung_dari_dpp_bukan_dari_nilai_pembayaran():
    """Rumusnya harus sama dengan rekap PPh, kalau tidak dua layar berbeda."""
    b = _blok(CTRL, "get_pph_position")
    assert re.search(r"dpp\s*\*\s*persen\)\s*/\s*100", b)


def test_tidak_ada_kompensasi_antar_masa():
    """
    Lebih bayar PPN dikreditkan ke masa berikutnya; PPh potongan TIDAK.
    Menyalin perlakuan PPN ke sini membuat masa yang sudah lunas tampak masih
    punya kredit.
    """
    b = _blok(CTRL, "get_pph_position")
    assert "saldo_kredit" not in b
    assert "kompensasi" not in b


# ----------------------------------------------------------------------
# Setoran
# ----------------------------------------------------------------------

def test_kode_setoran_pph_terpisah_dua():
    from repository.expense_repository import ExpenseRepository

    assert ExpenseRepository.KODE_SETORAN_PPH_POTONG == "5.1.8.2"
    assert ExpenseRepository.KODE_SETORAN_PPH_GAJI == "5.1.8.3"
    assert ExpenseRepository.KODE_SETORAN_PPN == "5.1.8.1"
    # Ketiganya harus berbeda; satu kode dipakai dua pajak membuat setoran
    # yang satu menutupi kekurangan yang lain.
    assert len({
        ExpenseRepository.KODE_SETORAN_PPN,
        ExpenseRepository.KODE_SETORAN_PPH_POTONG,
        ExpenseRepository.KODE_SETORAN_PPH_GAJI,
    }) == 3


def test_setoran_dikelompokkan_menurut_masa_yang_ditanggung():
    """
    PPh masa Juni disetor pada Juli. Mengelompokkan menurut tanggal setor
    membuat masa Juni selamanya tampak belum dibayar.
    """
    b = _blok(REPO, "get_setoran_pajak")
    assert "masa_pajak_efektif()" in b
    assert 'func.extract("month", masa) == month' in b


def test_kueri_setoran_tidak_disalin_dua_kali():
    """
    Dua salinan berarti satu di antaranya pasti tertinggal ketika perlakuan
    masanya disesuaikan — dan dua layar pajak akan menjawab berbeda atas masa
    yang sama.
    """
    b = _blok(CTRL, "get_pph_position")
    assert b.count("get_setoran_pajak(") == 2, (
        "posisi PPh tidak memakai kueri setoran bersama"
    )


def test_beban_belum_dibayar_bukan_setoran_yang_dibayar():
    b = _blok(CTRL, "get_pph_position")
    assert 'r.get("isPaid")' in b, (
        "setoran yang baru tercatat tetapi belum dibayar tidak dibedakan"
    )
