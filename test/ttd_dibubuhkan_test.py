"""
TANDA TANGAN DIBUBUHKAN pada CoP dan BAP.

"PO COP BAP kalau sudah di sign, bubuhkan tanda tangannya kalau available"

Yang dijaga di sini, dan dua di antaranya gagal dengan DIAM:

  1. Gambarnya hanya dibubuhkan bila lembarnya MEMANG SUDAH DISETUJUI.
     Tanpa syarat itu, CoP yang belum disetujui tercetak lengkap dengan
     tanda tangan direktur di bawahnya — dokumen yang tidak dapat dibedakan
     dari yang sah begitu keluar dari pencetak, dan satu lembar yang sampai
     ke pemasok sudah cukup untuk ditagihkan.

  2. Tidak punya tanda tangan BUKAN kegagalan. Lembarnya tercetak persis
     seperti sebelum fitur ini ada: kolom bergaris untuk ditandatangani
     tangan. Sebagian orang memang belum menyiapkannya, dan dokumen tidak
     boleh menunggu mereka.

  3. TINGGI blok tanda tangannya tetap, bertanda tangan maupun tidak.
     Blok yang meninggi dapat mendorong lembarnya ke halaman berikutnya —
     dan yang mencetak tidak akan menghubungkan halaman baru itu dengan
     tanda tangan yang baru dipasang seseorang kemarin.

  4. Gambarnya diambil SERVER saat merender. Bila ia melewati layar lebih
     dulu, stempelnya sudah berada di peramban orang dan dapat dipakai pada
     dokumen apa pun di luar sistem ini.
"""

import base64
import io
import re
from pathlib import Path

from PIL import Image, ImageDraw

from services.pdf_service import _lengkapi, _lingkungan_cop

AKAR = Path(__file__).resolve().parents[1]


def ttd() -> str:
    img = Image.new("RGBA", (720, 240), (0, 0, 0, 0))
    ImageDraw.Draw(img).line(
        [(60, 180), (200, 60), (340, 190)], fill=(17, 24, 39, 255), width=6
    )
    b = io.BytesIO()
    img.save(b, "PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def _render_bap(**tambahan):
    env = _lingkungan_cop()
    konteks = {
        "bap": [],
        "bapAdaPlafon": False,
        "bapAdaHargaSatuan": False,
        "bapTotal": {
            "bobot": 0.0,
            "bobotSebelumnya": 0.0,
            "bobotSaatIni": 0.0,
            "bobotAkumulatif": 0.0,
        },
        "cop": {},
        "spk": {},
        "perusahaan": {"nama": "PT Alpha"},
        "nomorBap": "001-042-R501-2026",
        "penandatanganBap": {},
        "keteranganPersetujuan": None,
        "logoDataUri": "",
    }
    konteks.update(tambahan)
    return env.get_template("cop_bap_isi.html").render(**konteks)


# ---------------------------------------------------------------------------
# 2. Tanpa tanda tangan: lembarnya tetap seperti dulu
# ---------------------------------------------------------------------------


def test_tanpa_tanda_tangan_lembarnya_tidak_berubah():
    keluar = _render_bap(
        penandatanganBap={"nama": "Stephanie", "jabatan": "Staf", "ttd": None}
    )
    assert "<img" not in keluar or "bt-ttd" not in keluar
    assert "Stephanie" in keluar


def test_dengan_tanda_tangan_gambarnya_ikut_tercetak():
    gambar = ttd()
    keluar = _render_bap(
        penandatanganBap={"nama": "Stephanie", "jabatan": "Staf", "ttd": gambar}
    )
    assert 'class="bt-ttd"' in keluar
    assert gambar[:60] in keluar


def test_penyetuju_bap_juga_dibubuhkan():
    gambar = ttd()
    keluar = _render_bap(
        cop={
            "bapApprovedByName": "Michael",
            "bapApprovedByPosition": "Direktur",
            "bapApprovedBySignature": gambar,
        }
    )
    assert keluar.count('class="bt-ttd"') == 1
    assert "Michael" in keluar


# ---------------------------------------------------------------------------
# 3. Tinggi bloknya tetap
# ---------------------------------------------------------------------------


def test_ruang_tanda_tangan_tingginya_tetap():
    """
    Bertanda tangan, jarak bawah nama badan MENGECIL dan digantikan tinggi
    gambarnya. Keduanya harus berjumlah kira-kira sama dengan ruang kosong
    yang dipakai bila tidak ada tanda tangan.
    """
    gaya = (AKAR / "templates" / "pdf" / "cop_bap_gaya.html").read_text(
        encoding="utf-8"
    )
    kosong = float(re.search(r"\.bt-badan \{ margin-bottom: ([\d.]+)pt", gaya).group(1))
    kecil = float(
        re.search(r"\.bt-badan--bertanda \{ margin-bottom: ([\d.]+)pt", gaya).group(1)
    )
    tinggi = float(re.search(r"\.bt-ttd \{[^}]*height: ([\d.]+)pt", gaya, re.S).group(1))
    bawah = float(
        re.search(r"\.bt-ttd \{[^}]*margin-bottom: ([\d.]+)pt", gaya, re.S).group(1)
    )

    assert abs((kecil + tinggi + bawah) - kosong) <= 4, (
        f"ruang bertanda {kecil + tinggi + bawah}pt vs kosong {kosong}pt"
    )


def test_ruang_tanda_tangan_cop_tingginya_juga_tetap():
    gaya = (AKAR / "templates" / "pdf" / "certificate_of_payment.html").read_text(
        encoding="utf-8"
    )
    kosong = float(re.search(r"\.ttd-badan \{ margin-bottom: ([\d.]+)pt", gaya).group(1))
    kecil = float(
        re.search(r"\.ttd-badan--bertanda \{ margin-bottom: ([\d.]+)pt", gaya).group(1)
    )
    tinggi = float(
        re.search(r"\.ttd-gambar \{[^}]*height: ([\d.]+)pt", gaya, re.S).group(1)
    )
    bawah = float(
        re.search(r"\.ttd-gambar \{[^}]*margin-bottom: ([\d.]+)pt", gaya, re.S).group(1)
    )

    assert abs((kecil + tinggi + bawah) - kosong) <= 4


# ---------------------------------------------------------------------------
# 1 & 4. Hanya yang sudah disetujui, dan diambil server
# ---------------------------------------------------------------------------


def test_lengkapi_meneruskan_gambar_ke_blok_penandatangan():
    keluar = _lengkapi(
        {
            "cop": {
                "approvedByName": "Michael",
                "approvedByPosition": "Direktur Utama",
                "approvedBySignature": "data:image/png;base64,AAA",
                "createdByName": "Stephanie",
                "createdBySignature": "data:image/png;base64,BBB",
            },
            "bap": [],
            "kontrak": {},
            "spk": {},
        }
    )
    assert keluar["penandatangan"]["ttd"] == "data:image/png;base64,AAA"
    assert keluar["penandatanganBap"]["ttd"] == "data:image/png;base64,BBB"


def test_controller_hanya_membubuhkan_yang_SUDAH_disetujui():
    """
    Syaratnya dibaca dari sumbernya, bukan dijalankan.

    Menjalankan `data_cetak` berarti menyiapkan seluruh CoP, SPK, adendum dan
    riwayatnya; yang diperiksa di sini satu syarat, dan syarat itu yang paling
    mudah hilang saat berkasnya disunting lagi.
    """
    isi = (
        AKAR / "controllers" / "certificate_of_payment_controller.py"
    ).read_text(encoding="utf-8")
    potong = isi[isi.index('"approvedBySignature"') : isi.index('"approvedBySignature"') + 400]
    assert 'cop.get("isApproved")' in potong, potong[:200]
    assert 'cop.get("isBapApproved")' in potong, potong[:400]


def test_gambar_diambil_repository_bukan_dikirim_layar():
    isi = (
        AKAR / "controllers" / "certificate_of_payment_controller.py"
    ).read_text(encoding="utf-8")
    assert "UserSignatureRepository.gambar_untuk" in isi
