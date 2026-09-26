"""
LEMBAR BAP untuk pekerjaan HARGA SATUAN.

Lembar Berita Acara Pemeriksaan menyatakan progres sebagai PERSENTASE terhadap
volume kontrak. Pada SPK tenaga kerja harga satuan tidak ada volume kontrak —
yang disepakati tarif per satuannya, dan volumenya baru diketahui saat
pekerjaannya berjalan.

Pembagi nol dijaga (`_bagi` mengembalikan nol), jadi tidak ada galat sama
sekali. Yang keluar lembar yang tercetak rapi, lengkap, siap ditandatangani —
dan berbunyi:

    Volume Kontrak 0 · Bobot 0% · Progres periode ini 0%

untuk pekerjaan yang volumenya justru sedang ditagihkan pada lembar yang sama.
Nol di sana bukan penyederhanaan; ia pernyataan yang keliru, dan ia yang
ditandatangani.

Yang benar tanda pisah: persentase terhadap sesuatu yang tidak ada BUKAN nol,
melainkan tidak ada.
"""

import os
import sys

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if AKAR not in sys.path:
    sys.path.insert(0, AKAR)

from services.pdf_service import _lingkungan_cop


def _baris(no, tanpa_plafon):
    """Satu baris BAP, sebagaimana controller menyusunnya."""
    return {
        "no": no,
        "pekerjaan": "Operator Drilling Rig",
        "keterangan": None,
        "adendum": None,
        "volumeKontrak": 0.0 if tanpa_plafon else 2.0,
        "satuan": "m'" if tanpa_plafon else "kali",
        "hargaSatuan": 35000.0,
        "total": 0.0 if tanpa_plafon else 2000000.0,
        "bobot": 0.0 if tanpa_plafon else 1.0,
        "volumeSebelumnya": 0.0,
        "persentaseSebelumnya": 0.0,
        "bobotSebelumnya": 0.0,
        "volumePeriodeIni": 2000.0 if tanpa_plafon else 1.0,
        "persentaseSaatIni": 0.0 if tanpa_plafon else 0.5,
        "bobotSaatIni": 0.0 if tanpa_plafon else 0.5,
        "volumeAkumulatif": 2000.0 if tanpa_plafon else 1.0,
        "persentaseAkumulatif": 0.0 if tanpa_plafon else 0.5,
        "bobotAkumulatif": 0.0 if tanpa_plafon else 0.5,
        "catatan": None,
        "tanpaPlafon": tanpa_plafon,
    }


KOSONG = {
    "bobot": 0.0,
    "bobotSebelumnya": 0.0,
    "bobotSaatIni": 0.0,
    "bobotAkumulatif": 0.0,
}


def _render(bap):
    env = _lingkungan_cop()
    return env.get_template("cop_bap_isi.html").render(
        bap=bap,
        bapAdaPlafon=any(not r["tanpaPlafon"] for r in bap),
        bapAdaHargaSatuan=any(r["tanpaPlafon"] for r in bap),
        bapTotal=KOSONG,
        cop={},
        spk={},
        perusahaan={},
        nomorBap="001-042-R501-2026",
        penandatanganBap=[],
        keteranganPersetujuan=None,
        logoDataUri="",
    )


def test_baris_harga_satuan_tidak_mencetak_nol_persen():
    """
    Persentase dan volume kontraknya bertanda pisah, BUKAN nol.

    Yang membaca lembar bertanda "0%" menyimpulkan pekerjaannya belum
    dikerjakan — pada lembar yang justru menagih 2.000 m'.
    """
    keluar = _render([_baris(1, tanpa_plafon=True)])
    assert "&mdash;" in keluar or "—" in keluar
    # Yang tercetak tinggal volume terlaksana; tidak ada satu pun "0,00%".
    assert "0,000%" not in keluar


def test_volume_terlaksana_tetap_tercetak_apa_adanya():
    """
    Yang dikosongkan hanya persentasenya.

    VOLUME-nya justru inti lembar ini — itu yang diperiksa di lapangan lalu
    ditandatangani. Mengosongkannya membuat lembarnya tidak ada gunanya.
    """
    keluar = _render([_baris(1, tanpa_plafon=True)])
    assert "2.000" in keluar


def test_baris_berplafon_tetap_mencetak_persentasenya():
    """
    Yang dikosongkan HANYA baris harga satuan.

    Bila tandanya terbaca per lembar, satu baris tanpa plafon akan
    mengosongkan seluruh kolom progres SPK itu — termasuk baris mobilisasi
    yang plafonnya jelas.
    """
    keluar = _render([_baris(1, tanpa_plafon=False)])
    assert "50,000%" in keluar


def test_total_bobot_tidak_berbunyi_nol_persen_pada_spk_harga_satuan():
    """
    Baris Total adalah angka PALING MENONJOL di lembar ini.

    Ia yang dibaca sebagai "pekerjaan ini sudah sekian persen". Pada SPK yang
    seluruh barisnya harga satuan, penyebutnya nol dan angka itu keluar
    "0,000%" — pada lembar yang justru sedang menagih 2.000 m'. Mengosongkan
    baris demi baris tetapi membiarkan totalnya nol berarti memperbaiki yang
    kecil dan meninggalkan yang besar.
    """
    keluar = _render([_baris(1, tanpa_plafon=True)])
    kaki = keluar[keluar.index("<tfoot>"):keluar.index("</tfoot>")]
    assert "0,000%" not in kaki
    assert "&mdash;" in kaki


def test_spk_campuran_menyebut_bahwa_totalnya_sebagian():
    """
    SPK D dapat punya keduanya: upah harga satuan dan mobilisasi berplafon.

    Bobot hanya dibagi sesama baris berplafon, sehingga mobilisasi tampak
    menyusun 100% kontrak sementara upah — yang nilainya jauh lebih besar —
    tidak terhitung sama sekali. Angkanya tidak dapat diperbaiki tanpa
    mengarang plafon; yang dapat dilakukan MENGATAKANNYA.
    """
    keluar = _render([
        _baris(1, tanpa_plafon=True),
        _baris(2, tanpa_plafon=False),
    ])
    assert "hanya mencakup pekerjaan yang" in keluar


def test_catatan_kaki_muncul_hanya_bila_ada_baris_harga_satuan():
    """
    Tanda pisah tanpa keterangan tidak dapat dibedakan dari data yang hilang.

    "Belum dikerjakan", "datanya hilang", dan "tidak berlaku" menuntun ke tiga
    pertanyaan yang berbeda, dan yang membaca lembar cetak tidak punya cara
    lain mengetahui yang mana.
    """
    dengan = _render([_baris(1, tanpa_plafon=True)])
    tanpa = _render([_baris(1, tanpa_plafon=False)])
    assert "HARGA SATUAN" in dengan
    assert "HARGA SATUAN" not in tanpa


def test_kunci_hilang_kembali_ke_perilaku_lama():
    """
    Pemanggil yang lupa mengirim `bapAdaPlafon` harus mendapat lembar LAMA.

    Bila kunci yang hilang mengosongkan baris Total, satu kekeliruan pemanggil
    terbaca di atas kertas sebagai kontrak yang tidak berplafon — dan lembar
    itu ditandatangani.
    """
    from services.pdf_service import _lingkungan_cop

    keluar = _lingkungan_cop().get_template("cop_bap_isi.html").render(
        bap=[_baris(1, tanpa_plafon=False)],
        bapTotal=KOSONG,
        cop={},
        spk={},
        perusahaan={},
        nomorBap="001-042-R501-2026",
        penandatanganBap=[],
        keteranganPersetujuan=None,
        logoDataUri="",
    )
    kaki = keluar[keluar.index("<tfoot>"):keluar.index("</tfoot>")]
    assert "0,000%" in kaki
    assert "&mdash;" not in kaki
