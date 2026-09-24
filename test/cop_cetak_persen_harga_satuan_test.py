"""
CETAK CoP — persentase pada SPK HARGA SATUAN.

SPK tenaga kerja (jenis D) menyepakati harga satuannya, bukan volumenya,
dan `purchase_order_items.quantity` di sana berisi 1 sebagai penambal.
"Nilai kontrak" yang terhitung karena itu cuma SATU SATUAN — Rp 120.000
untuk SPK yang setahun membayar puluhan juta.

Setiap persentase yang memakainya sebagai penyebut tidak menyatakan apa
pun. Yang benar-benar tercetak pada lembar produksi:

    Progress Kontrak   300.00%  x  Rp 120.000,00  =  Rp 360.000,00
    Pembayaran 2       700.00%
    Pembayaran 4       733.33%

Tujuh ratus persen di lembar yang ditandatangani dua pihak bukan cuma
jelek dipandang — ia angka yang terbaca, dan yang membacanya tidak punya
cara mengetahui bahwa penyebutnya memang tidak ada.

Yang dijaga berkas ini ADA TIGA, dan yang ketiga paling mudah terlanggar:

  1. pada SPK D persentasenya hilang;
  2. NILAI RUPIAHNYA tetap tercetak utuh — yang dibuang cuma persennya;
  3. pada jenis SPK LAIN tidak ada yang berubah sama sekali.
"""

import pytest

from services.pdf_service import _lengkapi, _lingkungan_cop

TOTAL = 120_000.0


def _data(jenis: str) -> dict:
    riwayat = [
        {"number": i, "name": f"00{i}-968-R501-2026", "date": "2026-08-01",
         "gross": n, "net": n}
        for i, n in enumerate([360_000.0, 840_000.0, 880_000.0], start=1)
    ]
    return {
        "cop": {
            "name": "015-968-R501-2026", "number": 15, "date": "2026-09-16",
            "periodStart": "2026-09-01", "periodEnd": "2026-09-15",
            "projectName": "R501", "approvedByName": "Daniel",
            "approvedByPosition": "GM", "isBapApproved": True,
            "isCopCreated": True, "isApproved": True,
        },
        "spk": {
            "name": "007-SPK-R501-D", "supplierName": "Atek Tri Tektona",
            "purchaseType": jenis, "dpPercentage": 0.0,
            "retentionPercentage": 0.0, "pphPercentage": 2.0, "ppn": 0.0,
        },
        "kontrak": {"induk": TOTAL, "adendum": 0.0, "total": TOTAL,
                    "adaAdendum": False, "daftarAdendum": []},
        "bap": [{
            "pekerjaan": "Operator Bored Pile", "unit": "hari",
            "volumeKontrak": 1, "volumeSebelumnya": 0, "volumeSaatIni": 7,
            "volumeAkumulatif": 7, "harga": 150_000.0, "bobot": 1.0,
            "bobotSebelumnya": 0.0, "bobotSaatIni": 3.0,
            "bobotAkumulatif": 3.0, "adendum": None, "tanpaPlafon": True,
            "nilai": 1_050_000.0,
        }],
        "bapAdaPlafon": False, "bapAdaHargaSatuan": True,
        "bapTotal": {"total": TOTAL, "bobot": 1.0, "bobotSebelumnya": 0.0,
                     "bobotSaatIni": 3.0, "bobotAkumulatif": 3.0},
        "nilai": {"kotor": 360_000.0, "persenProgres": 3.0, "potongan": 0.0,
                  "tambahan": 0.0, "bersih": 360_000.0, "tarifPpn": 0.0,
                  "ppn": 0.0, "tarifPph": 2.0, "pph": 7_200.0,
                  "tagihan": 360_000.0, "totalDibayar": 352_800.0},
        "penyesuaian": [], "pengurangan": {"pokok": [], "lain": []},
        "dpKontrak": 0.0, "riwayat": riwayat,
    }


def _cetak(jenis: str) -> str:
    env = _lingkungan_cop()
    templat = env.get_template("certificate_of_payment.html")
    return templat.render(**_lengkapi(_data(jenis)), sertakanBap=False)


def _rapat(teks: str) -> str:
    """
    Spasi berurutan dijadikan satu.

    Kalimat di dalam templat DIPENGGAL oleh pembungkus baris editor, jadi
    "HARGA SATUAN" tersimpan sebagai "HARGA\n            SATUAN". Mencari
    substring mentah akan gagal pada kalimat yang jelas-jelas ada — dan
    yang memperbaikinya akan mengira catatan kakinya hilang.
    """
    return " ".join(teks.split())


# --------------------------------------------------------------------- #
# penandanya
# --------------------------------------------------------------------- #
def test_jenis_D_dinyatakan_tanpa_plafon():
    assert _lengkapi(_data("D"))["kontrakBerplafon"] is False
    # Huruf kecil dan spasi ikut dikenali — nilainya datang dari basis data.
    assert _lengkapi(_data("d"))["kontrakBerplafon"] is False
    assert _lengkapi(_data(" D "))["kontrakBerplafon"] is False


@pytest.mark.parametrize("jenis", ["A", "B", "C", "F", "G", "H1", "H2", "511"])
def test_jenis_lain_tetap_berplafon(jenis):
    assert _lengkapi(_data(jenis))["kontrakBerplafon"] is True


def test_penanda_memakai_himpunan_yang_SAMA_dengan_penegak_pagu():
    """
    Satu sumber kebenaran. Disalin sebagai huruf "D" di dua tempat,
    keduanya akan berselisih diam-diam begitu salah satu berubah.
    """
    from repository.certificate_of_payment_repository import (
        JENIS_BOLEH_TANPA_PAGU,
    )

    for jenis in JENIS_BOLEH_TANPA_PAGU:
        assert _lengkapi(_data(jenis))["kontrakBerplafon"] is False


# --------------------------------------------------------------------- #
# lembarnya
# --------------------------------------------------------------------- #
def test_lembar_D_tidak_memuat_persentase_ngawur():
    html = _cetak("D")
    for ngawur in ("300.00%", "700.00%", "733.33%"):
        assert ngawur not in html, ngawur


def test_lembar_D_TETAP_memuat_nilai_rupiahnya():
    """
    Yang dibuang persennya, BUKAN uangnya. Membuang keduanya membuat lembar
    tagihan kehilangan angka yang justru menjadi isinya.
    """
    html = _cetak("D")
    for uang in ("360,000.00", "840,000.00", "880,000.00", "2,080,000.00"):
        assert uang in html, uang


def test_lembar_D_MENERANGKAN_kolom_yang_dikosongkan():
    # Kolom kosong tanpa keterangan terbaca sebagai "datanya hilang".
    html = _rapat(_cetak("D"))
    assert "menyepakati HARGA SATUAN, bukan volume" in html
    assert "tidak ada nilai kontrak yang dapat dijadikan penyebut" in html


def test_lembar_JENIS_LAIN_tidak_berubah():
    html = _cetak("H2")
    assert "300.00%" in html
    assert "700.00%" in html
    # Dan tidak kebagian catatan kaki yang bukan miliknya.
    assert "menyepakati HARGA SATUAN" not in _rapat(html)


def test_penanda_HILANG_mengembalikan_perilaku_lama():
    """
    Kunci yang hilang adalah kekeliruan pemanggil, bukan pernyataan bahwa
    kontraknya tanpa plafon. Lembarnya harus kembali mencetak persentase —
    bukan mengosongkan kolom persen pada SELURUH dokumen.
    """
    env = _lingkungan_cop()
    templat = env.get_template("certificate_of_payment.html")
    konteks = _lengkapi(_data("H2"))
    konteks.pop("kontrakBerplafon")
    html = templat.render(**konteks, sertakanBap=False)
    assert "300.00%" in html
