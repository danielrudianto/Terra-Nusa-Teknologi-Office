"""
SETORAN PPN pada laporan Posisi PPN.

Posisi PPN menjawab "berapa yang terutang". Ia tidak tahu apa-apa soal yang
sudah dibayar, sehingga masa yang sudah disetor lunas tetap tampil merah
kurang bayar — angkanya benar sebagai perhitungan, keliru sebagai keterangan
keadaan, dan yang membacanya menyimpulkan masih ada utang yang sudah lunas.

Yang dijaga di sini adalah keputusan-keputusan yang mudah terbalik saat
berkasnya disentuh lagi, dan yang bila terbalik tidak menimbulkan galat apa
pun: hanya satu layar yang diam-diam mengabarkan keadaan uang yang salah.
"""

import os
import re

import pytest

from utils.pajak import TOLERANSI_SETORAN, status_setoran

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(AKAR, "repository", "expense_repository.py")
CONTROLLER = os.path.join(AKAR, "controllers", "tax_controller.py")


def _sumber(path: str) -> str:
    return open(path, encoding="utf-8").read()


# --------------------------------------------------------------------------
# Kesimpulan keadaan setoran
# --------------------------------------------------------------------------


def test_tanpa_setoran_bukan_lunas():
    """
    Masa nihil BUKAN lunas.

    Godaannya menyimpulkan lunas dari "sisa nol", dan pada masa yang tidak
    menagih apa-apa sisanya memang nol. Layarnya lalu mengabarkan pembayaran
    yang tidak pernah ada.
    """
    assert status_setoran(0, 0) == "belum"
    assert status_setoran(825_186, 0) == "belum"


def test_selisih_pembulatan_tetap_lunas():
    """
    Kasus nyatanya: masa Juni 2026 terutang 825.186, disetor 825.192.

    Yang terutang dijumlahkan dari DPP × persen atas puluhan dokumen sehingga
    berekor pecahan; yang disetor satu angka bulat yang diketik ke SSP.
    Keduanya nyaris tidak pernah sama persis, dan tanpa toleransi setiap masa
    yang sudah lunas akan dilaporkan "lebih bayar Rp 6".
    """
    assert status_setoran(825_186, 825_192) == "lunas"
    assert status_setoran(825_192, 825_186) == "lunas"


def test_toleransi_tidak_menelan_kekurangan_sungguhan():
    """
    Toleransinya untuk pembulatan, bukan untuk menutupi kurang bayar.

    Bila ia melebar, kekurangan yang sungguhan akan dilaporkan lunas — dan
    itulah satu-satunya jenis kesalahan di layar ini yang berakhir pada
    denda.
    """
    assert TOLERANSI_SETORAN <= 1000
    assert status_setoran(10_000_000, 5_000_000) == "kurang"
    assert status_setoran(10_000_000, 9_998_000) == "kurang"


def test_setoran_berlebih_dinyatakan_apa_adanya():
    """Kelebihan setor bukan lunas; ia perlu terbaca supaya dapat ditelusuri."""
    assert status_setoran(1_000_000, 3_000_000) == "lebih"


@pytest.mark.parametrize("sisa", [TOLERANSI_SETORAN, -TOLERANSI_SETORAN])
def test_batas_toleransi_termasuk_lunas(sisa):
    """Tepat di batas masih lunas — batasnya inklusif, di kedua arah."""
    assert status_setoran(1_000_000 + sisa, 1_000_000) == "lunas"


# --------------------------------------------------------------------------
# Cara setorannya dikenali dan dicocokkan
# --------------------------------------------------------------------------


def test_setoran_dikenali_dari_kode_akun():
    """
    Dicocokkan menurut KODE akun, bukan nama lawan transaksinya.

    "Penerimaan Negara (PPN)" adalah data yang diketik orang: satu huruf
    berbeda, atau satu lawan transaksi baru dibuat, dan pencocokannya berhenti
    bekerja tanpa memberi tanda apa pun — laporannya cuma berubah menjadi
    "belum disetor".
    """
    s = _sumber(REPO)
    assert 'KODE_SETORAN_PPN = "5.1.8.1"' in s, "kode akun setoran PPN tidak ada"
    blok = s[s.index("async def get_setoran_ppn(") :]
    blok = blok[: blok.find("\n    @staticmethod")]
    assert "KODE_SETORAN_PPN" in blok, "kuerinya tidak memakai kode akunnya"
    assert "name ==" not in blok, "jangan mencocokkan menurut nama lawan transaksi"


def test_hanya_ppn_bukan_seluruh_pajak():
    """
    5.1.8.x seluruhnya pajak; hanya `.1` yang PPN.

    Bila kodenya dipotong menjadi "5.1.8", setoran PPh 21, PPh 23, SPT
    tahunan, dan denda pajak ikut terhitung sebagai setoran PPN — dan masa
    yang belum disetor akan tampil lunas.
    """
    s = _sumber(REPO)
    m = re.search(r'KODE_SETORAN_PPN\s*=\s*"([\d.]+)"', s)
    assert m, "kode setoran PPN tidak ditemukan"
    assert m.group(1) == "5.1.8.1", (
        f'kode setoran PPN menjadi "{m.group(1)}"; kode yang lebih pendek '
        "ikut menangkap PPh dan denda pajak"
    )


def test_setoran_dicocokkan_menurut_masa_yang_ditanggung():
    """
    PPN masa Juni disetor pada Juli.

    Yang dicari layar ini adalah setoran UNTUK Juni, jadi pencocokannya harus
    memakai `COALESCE(masaPajak, date)` — sama seperti seluruh laporan PPN
    lain. Memakai tanggal setornya membuat setoran itu muncul pada masa Juli,
    yaitu masa yang justru belum disetor.
    """
    s = _sumber(REPO)
    blok = s[s.index("async def get_setoran_ppn(") :]
    blok = blok[: blok.find("\n    @staticmethod")]
    assert "masa_pajak_efektif()" in blok, (
        "setoran dicocokkan bukan menurut masa pajak efektif"
    )
    assert 'func.extract("month", masa)' in blok
    assert 'func.extract("year", masa)' in blok


def test_setoran_belum_dibayar_tidak_disaring_diam_diam():
    """
    `isPaid` dibawa apa adanya, bukan dipakai menyaring.

    Beban yang tercatat tetapi belum dibayar memang bukan setoran — tetapi
    membuangnya di kueri membuat barisnya hilang sama sekali, dan yang
    bertanya "kenapa setoran saya tidak muncul" tidak menemukan apa pun.
    Layarnya yang memutuskan bagaimana menyebutnya.
    """
    s = _sumber(REPO)
    blok = s[s.index("async def get_setoran_ppn(") :]
    blok = blok[: blok.find("\n    @staticmethod")]
    assert "e.isPaid," in blok, "isPaid tidak ikut dikembalikan"
    assert "e.isPaid ==" not in blok, "isPaid dipakai menyaring baris"


def test_batas_masa_awal_berlaku_juga_untuk_setoran():
    """
    Batas 2025 berlaku di sini juga.

    Bila tidak, setoran era e-Faktur lama tetap dapat muncul pada laporan yang
    seluruh angka lainnya sudah dipotong pada 2025 — satu-satunya baris yang
    berasal dari data yang sengaja tidak disajikan.
    """
    s = _sumber(REPO)
    blok = s[s.index("async def get_setoran_ppn(") :]
    blok = blok[: blok.find("\n    @staticmethod")]
    assert "MASA_PAJAK_AWAL" in blok


# --------------------------------------------------------------------------
# Bentuk jawaban ke layar
# --------------------------------------------------------------------------


def test_posisi_ppn_membawa_setoran_dan_sisanya():
    """
    Layar tidak menghitung sendiri sisanya maupun kesimpulannya.

    Keduanya pernyataan tentang uang; bila layarnya menyusunnya sendiri, ia
    akan menjawab berbeda dari laporan lain atas angka yang sama — termasuk
    soal berapa selisih pembulatan yang masih dianggap lunas.
    """
    s = _sumber(CONTROLLER)
    for kunci in ('"setoran"', '"sisaSetelahSetoran"', '"dibayar"'):
        assert kunci in s, f"{kunci} tidak ada pada jawaban posisi PPN"
    assert "status_setoran(selisih, setoran_total)" in s, (
        "kesimpulan setoran tidak diambil dari utils.pajak"
    )
