"""
Awalan nomor purchase order.

Nomor harus menyebut dokumen yang benar-benar terbit. Pernah seluruh jenis
memakai "SPK", sehingga pembelian beton tercetak berjudul PURCHASE ORDER
tetapi bernomor `013-SPK-MICZ-F` — vendor menerima dua sebutan berbeda pada
satu lembar yang sama.

Empat jenis bentuknya bergantung isian, bukan kodenya saja, dan nama kunci
penentunya berbeda tiap formulir. Diuji satu per satu karena menebak satu
nama membuat tiga lainnya salah tanpa galat apa pun.
"""

import os

os.environ.setdefault("DATABASE_URL", "mysql://uji:uji@localhost/uji")

from controllers.purchase_order_controller import PurchaseOrderController


def awalan(jenis, custom=None):
    return PurchaseOrderController._awalan_dokumen(jenis, custom or {})


def test_pengadaan_barang_memakai_po():
    for jenis in ("G", "C", "5.1.1", "5.1.6"):
        assert awalan(jenis) == "PO", jenis


def test_jasa_memakai_spk():
    for jenis in ("A", "B", "D", "H", "6.4.1", "6.4.2", "6.5.2", "5.1.12"):
        assert awalan(jenis) == "SPK", jenis


def test_po_f_mengikuti_jenis_material():
    """Pengadaan material tetap PO; jasa pengujian menjadi SPK."""
    for material in ("beton", "besi", "lain"):
        assert awalan("F", {"materialType": material}) == "PO", material
    for material in ("ujitekan", "ujibesi"):
        assert awalan("F", {"materialType": material}) == "SPK", material


def test_jenis_bergantung_isian():
    """Nama kunci penentunya berbeda tiap formulir."""
    assert awalan("5.1.2", {"maintenanceMode": "barang"}) == "PO"
    assert awalan("5.1.2", {"maintenanceMode": "jasa"}) == "SPK"
    assert awalan("6.3.2", {"marketingMode": "barang"}) == "PO"
    assert awalan("6.3.1", {"marketingMode": "jasa"}) == "SPK"
    assert awalan("6.5.1", {"recruitmentMode": "kuota"}) == "PO"
    assert awalan("6.5.1", {"recruitmentMode": "borongan"}) == "SPK"


def test_tanpa_penentu_jatuh_ke_spk():
    """
    Jenis bergantung isian yang datanya tidak lengkap dianggap jasa.

    Dokumen lama tidak selalu menyimpan penentunya. SPK dipilih sebagai
    cadangan karena itulah bentuk yang berlaku sebelum pemisahan ini.
    """
    assert awalan("5.1.2") == "SPK"
    assert awalan("6.3.2") == "SPK"
    assert awalan("6.5.1") == "SPK"

def test_varian_h_tetap_spk():
    """
    H1 dan H2 tetap SURAT PERINTAH KERJA.

    PO-H menyimpan jenisnya sebagai "H1" (subkontraktor badan usaha) atau
    "H2" (perorangan) — perbedaan yang menentukan ISI dokumennya, bukan
    jenis dokumennya. Keduanya pekerjaan subkontrak, dan lembarnya berjudul
    SURAT PERINTAH KERJA.

    Tanpa peringkasan varian, "H1" tidak pernah cocok dengan "H" pada
    `JENIS_SPK`, sehingga nomornya terbit sebagai `013-PO-MICZ-H1` di atas
    lembar berjudul SPK — vendor menerima dua sebutan berbeda pada satu
    lembar yang sama.

    Akar yang sama pernah membuat pratinjau PO-H tampil tanpa satu klausul
    pun, karena pencarian templat juga mencocokkan ke "H".
    """
    for jenis in ("H", "H1", "H2"):
        assert awalan(jenis) == "SPK", jenis


def test_varian_tidak_mengubah_jenis_lain():
    """Peringkasan varian tidak boleh menyentuh jenis yang bukan varian."""
    assert awalan("G") == "PO"
    assert awalan("C") == "PO"
    assert awalan("A") == "SPK"
    assert awalan("6.4.1") == "SPK"


def test_setiap_varian_menunjuk_jenis_yang_dikenal():
    """
    Jenis dasar tiap varian harus benar-benar ada.

    Salah tulis pada peta varian tidak menimbulkan galat apa pun — kodenya
    hanya tidak pernah cocok, dan awalannya diam-diam kembali ke "PO".
    """
    from controllers.purchase_order_controller import PurchaseOrderController as C

    dikenal = C.JENIS_SPK | {"C", "F", "G", "5.1.1", "5.1.2", "5.1.6",
                             "6.3.1", "6.3.2", "6.5.1"}
    for varian, dasar in C.VARIAN_JENIS.items():
        assert dasar in dikenal, f"{varian} -> {dasar} tidak dikenal"
