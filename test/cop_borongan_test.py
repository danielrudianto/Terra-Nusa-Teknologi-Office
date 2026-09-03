"""
CoP atas SPK BORONGAN.

SPK lump sum menyimpan nilainya di `customData.lumpSumPrice`; baris
pekerjaannya sengaja berharga NOL — layar pembuatannya memaksa `price: 0`
begitu jenisnya dipilih borongan, sebab satu nilai berlaku untuk seluruh
lingkup.

Harga CoP selalu diambil dari harga baris SPK — aturan yang benar, dan yang
menahan angka mengada-ada dari layar. Tetapi pada SPK borongan harga baris itu
nol, sehingga SELURUH CoP atas SPK borongan lahir bernilai Rp 0. Tidak ada
galat sama sekali: volumenya sah, pagunya cukup, dokumennya tercetak rapi.
Hanya nilainya nol — dan itu lembar yang ditandatangani vendor lalu ditagihkan.

Sudah pernah terjadi pada dialog lihat purchase order (lihat
`nilai_borongan_test.py`); ini kejadian yang sama di tempat yang berbeda.
"""

import os
from decimal import Decimal

from repository.certificate_of_payment_repository import (
    _custom,
    _nilai_borongan,
)

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(
    AKAR, "repository", "certificate_of_payment_repository.py"
)
CONTROLLER = os.path.join(
    AKAR, "controllers", "certificate_of_payment_controller.py"
)


def _sumber(path):
    return open(path, encoding="utf-8").read()


# --------------------------------------------------------------------------
# Membaca nilai borongan
# --------------------------------------------------------------------------


def test_customdata_terbaca_baik_sebagai_dict_maupun_teks():
    """
    Kolomnya JSON dan biasanya sudah terurai sendiri, tetapi sebagian baris
    lama tersimpan sebagai TEKS.

    Yang membaca dengan mengandaikan salah satunya bekerja pada sebagian
    dokumen saja — dan yang gagal tidak menimbulkan galat, hanya nilai yang
    lenyap.
    """
    assert _custom({"rateType": "lumpsum"})["rateType"] == "lumpsum"
    assert _custom('{"rateType": "lumpsum"}')["rateType"] == "lumpsum"
    assert _custom(None) == {}
    assert _custom("bukan json") == {}


def test_hanya_borongan_yang_punya_nilai():
    """SPK harga satuan memakai harga barisnya apa adanya."""
    assert _nilai_borongan({"rateType": "unit", "lumpSumPrice": 999}) is None
    assert _nilai_borongan({}) is None


def test_nilai_borongan_dibaca_dari_lumpsumprice():
    """Bentuk dari dokumen sungguhan: SPK 007-SPK-MCHP-H2, Rp 4.000.000."""
    custom = {"rateType": "lumpsum", "lumpSumPrice": 4000000}
    assert _nilai_borongan(custom) == Decimal("4000000")


def test_rate_type_tidak_peka_huruf_besar():
    assert _nilai_borongan({"rateType": "LumpSum", "lumpSumPrice": 10}) == 10


# --------------------------------------------------------------------------
# Cara nilainya turun ke baris
# --------------------------------------------------------------------------


def test_harga_dibagi_volume_kontrak_bukan_dipasang_utuh():
    """
    Dibagi volume kontraknya, sehingga progres SEBAGIAN bekerja sendirinya.

    Pada SPK borongan Rp 4 juta dengan pagu 1 LS, harga barisnya menjadi 4
    juta; separuh volume menghasilkan 2 juta tanpa aturan terpisah. Bila
    nilainya dipasang utuh sebagai harga, setiap CoP sebagian akan menagih
    nilai penuh.
    """
    s = _sumber(REPO)
    assert "borongan[po_id] / pagu" in s, (
        "nilai borongan tidak dibagi volume kontrak"
    )


def test_pagu_nol_tidak_membagi():
    """Pembagian dengan nol menjatuhkan seluruh permintaan, bukan satu baris."""
    s = _sumber(REPO)
    i = s.index("borongan[po_id] / pagu")
    konteks = s[max(0, i - 400) : i]
    assert "pagu > 0" in konteks, "pembagian tidak dijaga terhadap pagu nol"


def test_borongan_banyak_baris_ditandai_bukan_dibagi_rata():
    """
    Satu nilai untuk seluruh lingkup tidak dapat dipecah ke baris tanpa dasar
    pembagian.

    Membagi rata adalah mengarang dasarnya, dan angkanya akan ditagihkan.
    Layar pembuatan SPK-H mengizinkan lingkup berbaris banyak pada borongan,
    jadi bentuk ini nyata — bukan kemungkinan teoretis.
    """
    s = _sumber(REPO)
    assert "boronganTakTerbagi" in s
    assert "jumlah_baris.get(po_id, 0) == 1" in s, (
        "nilai borongan diturunkan tanpa memeriksa jumlah barisnya"
    )


def test_borongan_tak_terbagi_ditolak_bukan_dinilai_nol():
    """
    CoP bernilai nol tetap dapat disetujui dan ditagihkan, dan tidak ada satu
    pun layar yang akan menyebutnya janggal. Karena itu ditolak dengan
    sebutan yang jelas, bukan dibiarkan lewat.
    """
    s = _sumber(CONTROLLER)
    assert 'b.get("boronganTakTerbagi")' in s
    i = s.index('b.get("boronganTakTerbagi")')
    lanjutan = s[i : i + 700]
    assert "app_error" in lanjutan, "tidak ditolak, hanya diperiksa"
    assert "ErrorCode.VALIDATION" in lanjutan


def test_harga_tetap_tidak_diambil_dari_kiriman_layar():
    """
    Aturan yang paling menjaga uang di berkas ini tidak boleh ikut longgar
    karena borongan ditangani.

    Harga selalu disusun dari SPK — entah dari harga barisnya atau dari nilai
    borongannya — tidak pernah dari `it`, yang datang dari peramban.
    """
    s = _sumber(CONTROLLER)
    i = s.index("async def _siapkan_items(")
    blok = s[i : s.find("\n    # ---", i)]
    assert 'it.get("price")' not in blok
    assert 'it["price"]' not in blok


# --------------------------------------------------------------------------
# Nama baris: SPK jasa vs baris MATERIAL
# --------------------------------------------------------------------------


class _Baris(dict):
    """Baris tiruan; `databases.Record` diakses seperti pemetaan."""

    def keys(self):
        return super().keys()


def test_nama_baris_jasa_dari_task():
    from repository.certificate_of_payment_repository import _nama_baris

    assert _nama_baris(_Baris(task="Pekerjaan Pembesian D40")) == (
        "Pekerjaan Pembesian D40"
    )


def test_nama_baris_material_dari_master_item():
    """
    Baris MATERIAL tidak mengisi `task` — ia menunjuk `master_item`.

    Sejak beton dilayani CoP, seluruh barisnya tampil "-" di layar pencatatan
    volume dan di lembar BAP: yang mengisi volume melihat kotak tanpa nama
    dan harus menebak mana yang mana.
    """
    from repository.certificate_of_payment_repository import _nama_baris

    b = _Baris(task=None, itemDescription="Beton K-300", equipmentName=None)
    assert _nama_baris(b) == "Beton K-300"


def test_task_menang_atas_nama_master():
    """Bila seseorang menuliskan uraiannya sendiri, itulah yang ia maksud."""
    from repository.certificate_of_payment_repository import _nama_baris

    b = _Baris(task="Beton K-300 zona A", itemDescription="Beton K-300")
    assert _nama_baris(b) == "Beton K-300 zona A"


def test_nama_kosong_tetap_none_bukan_string_kosong():
    from repository.certificate_of_payment_repository import _nama_baris

    assert _nama_baris(_Baris(task="   ", itemDescription=None)) is None


def test_nama_diambil_lewat_join_bukan_task_saja():
    """Kedua pembaca baris SPK harus ikut menjoin nama masternya."""
    s = _sumber(REPO)
    assert s.count("LEFT JOIN master_item") >= 2, (
        "hanya satu pembaca yang menjoin nama material"
    )
    assert s.count("LEFT JOIN master_equipment") >= 2


# --------------------------------------------------------------------------
# Nilai kontrak
# --------------------------------------------------------------------------


def test_nilai_kontrak_borongan_tidak_dari_penjumlahan_baris():
    """
    Nilai kontrak bukan angka yang berhenti di lembar cetak.

    Pagu uang muka dan pagu retensi dihitung sebagai persentase DARINYA, jadi
    nol di sini berarti uang muka dan retensi ikut nol tanpa pernah menyebut
    alasannya.
    """
    s = _sumber(REPO)
    i = s.index("async def nilai_kontrak(")
    blok = s[i : s.find("\n    @staticmethod", i)]
    assert "_peta_borongan" in blok, "nilai kontrak tidak mengenal SPK borongan"
    assert "GROUP BY purchaseOrderID" in blok, (
        "dijumlahkan sekaligus atas rantai; satu rantai boleh bercampur "
        "borongan dan harga satuan"
    )


def test_satu_tempat_membaca_nilai_borongan():
    """
    `pagu`, `baris_kontrak`, dan `nilai_kontrak` membaca dari pembantu yang
    sama.

    Bila masing-masing membacanya sendiri, ketiganya akan berselisih pada
    perubahan berikutnya: layar menyebut satu angka, lembar cetak angka lain,
    pagu uang muka angka ketiga.
    """
    s = _sumber(REPO)
    assert s.count("_peta_borongan(ids)") >= 3
