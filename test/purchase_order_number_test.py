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


# ---------------------------------------------------------------- adendum


def _nomor_adendum(kode, jenis, urut_induk, ke):
    """Bentuk nomor adendum tanpa menyentuh basis data."""
    import asyncio

    from controllers.purchase_order_controller import PurchaseOrderController as C

    return asyncio.run(
        C.generate_purchase_order_name(kode, jenis, None, urut_induk, ke)
    )[0]


def test_nomor_adendum_sesuai_dokumen_terbit():
    """
    Bentuknya diverifikasi terhadap delapan dokumen yang sudah terbit.

    Urutan, kode proyek, dan jenisnya SAMA dengan induknya — itulah yang
    menjadikannya adendum atas dokumen tersebut, bukan dokumen lain yang
    berdiri sendiri. `ADD{n}` diselipkan pada posisi kedua.
    """
    assert _nomor_adendum("BPBP", "F", 13, 1) == "013-ADD1-PO-BPBP-F"
    assert _nomor_adendum("MICZ", "D", 1, 2) == "001-ADD2-SPK-MICZ-D"
    assert _nomor_adendum("TSKBP", "H1", 250, 1) == "250-ADD1-SPK-TSKBP-H1"
    assert _nomor_adendum("DPTCC", "H2", 25, 1) == "025-ADD1-SPK-DPTCC-H2"
    assert _nomor_adendum("R35CH", "F", 11, 1) == "011-ADD1-PO-R35CH-F"


def test_adendum_tidak_mengubah_awalan_induknya():
    """
    Adendum SPK tetap SPK, adendum PO tetap PO.

    Awalannya ditentukan jenis dokumennya, dan jenis itu tidak berubah
    karena ada adendum.
    """
    assert "-SPK-" in _nomor_adendum("MICZ", "D", 1, 1)
    assert "-PO-" in _nomor_adendum("BPBP", "F", 13, 1)
    assert "-SPK-" in _nomor_adendum("TSKBP", "H1", 250, 1)


def test_nomor_urut_adendum_dari_max_bukan_count():
    """
    Urutan adendum dihitung dari MAX, bukan COUNT.

    Adendum yang dihapus lunak tetap pernah terbit dan nomornya sudah
    dipegang vendor; memakai COUNT akan menerbitkan `ADD2` untuk kedua
    kalinya setelah satu adendum dihapus.
    """
    import os

    p = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "repository",
        "purchase_order_repository.py",
    )
    s = open(p).read()
    i = s.index("async def next_addendum_number")
    blok = s[i : s.index("async def", i + 10)]
    assert "MAX(addendumNumber)" in blok
    assert "COUNT(" not in blok


def test_adendum_tanpa_urutan_induk_ditolak():
    """
    Induk yang nomornya diketik manual tidak punya urutan.

    Membiarkannya lolos menghasilkan nomor adendum tanpa urutan — dan nomor
    itu tidak dapat ditelusuri kembali ke induknya.
    """
    import os

    p = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "controllers",
        "purchase_order_controller.py",
    )
    s = open(p).read()
    assert "Parent purchase order has no sequence number" in s


# ------------------------------------------------- batas perubahan adendum


def _beda(induk, baru):
    from controllers.purchase_order_controller import PurchaseOrderController as C

    return C._periksa_kunci_adendum(induk, baru)


INDUK = {
    "supplierID": 118,
    "projectName": "R501",
    "purchaseType": "F",
    "customData": '{"materialType": "besi"}',
}


def _dengan(**ubah):
    baru = {
        "supplierID": 118,
        "projectName": "R501",
        "purchaseType": "F",
        "customData": {"materialType": "besi"},
    }
    baru.update(ubah)
    return baru


def test_adendum_sama_persis_lolos():
    assert _beda(INDUK, _dengan()) == []


def test_adendum_tidak_boleh_ganti_pemasok():
    """
    Mengganti pemasok berarti menagih pihak lain atas dokumen bernomor sama.

    Lembar `013-PO-BPBP-F` sudah ditandatangani satu vendor; adendumnya
    bernomor sama dan karena itu terikat pada vendor yang sama.
    """
    assert _beda(INDUK, _dengan(supplierID=999))


def test_adendum_tidak_boleh_ganti_proyek():
    """
    Mengganti proyek memindahkan biayanya ke pembukuan proyek lain tanpa
    jejak — dan laporan margin kedua proyek ikut salah.
    """
    assert _beda(INDUK, _dengan(projectName="MICZ"))


def test_adendum_tidak_boleh_ganti_jenis_material():
    """
    Jenis material menentukan JUDUL dokumennya.

    Beton dan besi terbit sebagai PURCHASE ORDER; uji tekan dan uji besi
    sebagai SURAT PERINTAH KERJA. Mengubahnya membuat nomor ber-"PO" terbit
    di atas lembar berjudul SURAT PERINTAH KERJA.
    """
    assert _beda(INDUK, _dengan(customData={"materialType": "ujitekan"}))


def test_adendum_tidak_boleh_ganti_jenis_po():
    assert _beda(INDUK, _dengan(purchaseType="G"))


def test_seluruh_perbedaan_dilaporkan():
    """Bukan hanya yang pertama; memperbaiki satu per satu melelahkan."""
    m = _beda(
        INDUK,
        _dengan(supplierID=1, projectName="X", purchaseType="A"),
    )
    assert len(m) == 3


def test_penentu_jenis_dokumen_terkunci_seluruhnya():
    """
    Daftar isian terkunci harus mencakup SELURUH penentu jenis dokumen.

    Bila `_awalan_dokumen` kelak membaca penentu baru dan daftar ini tidak
    ikut diperbarui, penentu itu dapat diubah pada adendum — dan nomor
    dokumennya bertentangan dengan judulnya tanpa galat apa pun.
    """
    import os
    import re

    from controllers.purchase_order_controller import PurchaseOrderController as C

    p = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "controllers",
        "purchase_order_controller.py",
    )
    s = open(p).read()
    i = s.index("def _awalan_dokumen")
    j = s.index("async def generate_purchase_order_name", i)
    dibaca = set(re.findall(r'c\.get\("(\w+)"\)', s[i:j]))
    terkunci = set(C.CUSTOM_TERKUNCI_ADENDUM)
    assert dibaca <= terkunci, f"belum terkunci: {sorted(dibaca - terkunci)}"
