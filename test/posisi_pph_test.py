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
REPO_SLIP = os.path.join(AKAR, "repository", "salary_slip_repository.py")
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


def test_tiap_bagian_menyebut_terutang_dan_rinciannya():
    """
    Dua kunci, bukan lima. Yang dibuang — setoran, sisanya, dan kesimpulan
    lunas/kurang — dijaga terpisah di bawah.
    """
    b = _blok(CTRL, "get_pph_position")
    for kunci in ('"terutang"', '"rows"', '"nama"'):
        assert kunci in b, f"bagian posisi tidak menyebut {kunci}"


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
# Setoran — TIDAK dilaporkan di sini
# ----------------------------------------------------------------------

def test_posisi_pph_tidak_menyebut_setoran():
    """
    Setorannya sempat dicari di antara beban dengan kode tertentu, lalu
    dikurangkan dari terutang untuk menyimpulkan "kurang setor" atau "lunas".

    Pemetaan kodenya tidak bertahan: setoran PPh tidak selalu tercatat sebagai
    beban berkode tersebut, sehingga angka yang muncul bukan berapa yang
    benar-benar disetor. Dan yang berbahaya bukan angkanya melainkan
    kesimpulannya — masa yang sebenarnya sudah disetor tampil sebagai "kurang
    setor", dan yang membacanya menyetor dua kali.

    Lebih baik tidak menyatakan apa pun tentang setoran daripada
    menyatakannya salah.
    """
    b = _blok(CTRL, "get_pph_position")
    for kata in ("get_setoran_pajak", "setoran_total", "setoranRows", "sisa"):
        assert kata not in b, (
            f"posisi PPh masih menghitung setoran ({kata})"
        )


def test_kesimpulan_setoran_tidak_disusun_untuk_pph():
    """
    `status_setoran` menjawab lunas/kurang/lebih. Dipakai di sini, ia
    menyatakan sesuatu tentang uang yang tidak diketahui sumbernya.
    """
    b = _blok(CTRL, "get_pph_position")
    assert "status_setoran" not in b
    assert "keadaan" not in b


def test_kode_setoran_pph_tidak_ada_lagi():
    """
    Konstantanya ikut dihapus, bukan sekadar tidak dipanggil.

    Konstanta yang tertinggal menyatakan pemetaan yang keliru sebagai
    fakta — dan yang membacanya nanti akan memakainya lagi.
    """
    from repository.expense_repository import ExpenseRepository

    assert not hasattr(ExpenseRepository, "KODE_SETORAN_PPH_POTONG")
    assert not hasattr(ExpenseRepository, "KODE_SETORAN_PPH_GAJI")


def test_kode_setoran_ppn_tetap_ada():
    """
    PPN berbeda: setorannya memang dicatat sebagai beban berkode itu, dan
    posisi PPN tetap memakainya. Yang dicabut hanya PPh.
    """
    from repository.expense_repository import ExpenseRepository

    assert ExpenseRepository.KODE_SETORAN_PPN == "5.1.8.1"


def test_terutang_beserta_rinciannya_tetap_dilaporkan():
    """Yang dibuang hanya setorannya; terutang dan rinciannya tetap."""
    b = _blok(CTRL, "get_pph_position")
    assert '"terutang"' in b
    assert '"rows"' in b


# ----------------------------------------------------------------------
# Masa PPh 21 — digeser satu bulan dari periode slipnya
# ----------------------------------------------------------------------

def test_periode_slip_untuk_masa():
    """
    Gaji Agustus dibayarkan September, dan PPh 21 terutang saat
    penghasilannya DIBAYARKAN. Masa September karena itu memuat slip Agustus.
    """
    from utils.pajak import periode_slip_untuk_masa as f

    assert f(9, 2026) == (8, 2026)
    assert f(12, 2026) == (11, 2026)


def test_masa_januari_menyeberang_tahun():
    """
    Satu-satunya masa yang menyeberang tahun. Pemanggil yang mengurangkan
    bulannya sendiri akan benar sebelas kali lalu salah sekali — tepat pada
    masa yang paling sibuk.
    """
    from utils.pajak import periode_slip_untuk_masa as f

    assert f(1, 2026) == (12, 2025)


def test_posisi_pph_mengambil_slip_masa_sebelumnya():
    """
    Sebelum ini satu layar memakai DUA arti "masa" sekaligus: sisi pembelian
    disaring dari tanggal PEMBAYARAN, sisi gaji dari periode slipnya sendiri.
    Dua arti untuk satu kata pada satu halaman.
    """
    b = _blok(CTRL, "get_pph_position")
    assert "periode_slip_untuk_masa(month, year)" in b
    assert "get_pph_report(\n                bulan_slip, tahun_slip\n            )" in b, (
        "posisi PPh masih mengambil slip bulan yang sama dengan masanya"
    )


def test_pergeseran_tidak_ditanam_di_repository():
    """
    Kueri yang sama dipakai laporan lain yang memang berbicara tentang slip
    bulan itu sendiri. Menggeser di repository memindahkan artinya untuk
    SEMUA pemanggil sekaligus, termasuk yang tidak diminta.
    """
    import io
    isi = io.open(REPO_SLIP, encoding="utf-8").read()
    assert "periode_slip_untuk_masa" not in isi
    assert "OFFSET_MASA_PPH21" not in isi


def test_unduhan_gaji_memakai_masa_yang_sama():
    """
    Keduanya tombol pada kartu yang sama. Bila yang satu berarti "masa" dan
    yang lain "periode slip", angka pada layar tidak akan pernah cocok dengan
    angka pada unduhannya — dan yang membandingkannya menyimpulkan salah
    satunya rusak.
    """
    b = _blok(CTRL, "get_pph_salary_report")
    assert "periode_slip_untuk_masa(month, year)" in b


def test_periode_slip_ikut_dikirim_ke_layar():
    """
    Yang membaca "Masa September" lalu melihat slip Agustus di rinciannya
    akan mengira ada yang keliru — padahal justru itu yang benar. Karena itu
    periodenya disebut, bukan dibiarkan ditebak.
    """
    b = _blok(CTRL, "get_pph_position")
    assert '"periodeSlip"' in b
