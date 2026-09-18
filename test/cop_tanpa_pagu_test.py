"""
SPK D HARGA SATUAN: kontrak tanpa plafon volume.

Layar SPK D dulu mengirim `quantity: 1` sebagai isian mati — formulirnya tidak
punya kotak volume sama sekali. Angka itu bukan kesepakatan siapa pun; ia
tersisa dari waktu ketika baris SPK D tidak pernah dibaca apa-apa.

Sejak pagu CoP dijaga, angka itu berubah menjadi PLAFON. Layar pencatatan
volume menyebut "Volume SPK 1 m'", dan setiap berita acara bervolume
sebenarnya — 2.000 m', 26 hari — ditolak. SPK yang sah, sudah ditandatangani,
berhenti dapat ditagih; dan penolakannya menunjuk angka yang tidak pernah
disepakati siapa pun.

Yang diuji di sini dua hal, dan keduanya harus memakai penanda YANG SAMA:
  * `_tanpa_pagu` memutuskan siapa yang tanpa plafon — hanya jenis D;
  * controller MELEWATI pemeriksaan sisa untuk baris bertanda itu.

Bila keduanya menghitung sendiri-sendiri, layar akan menampilkan baris yang
terbuka lalu penyimpanannya ditolak — atau sebaliknya, dan yang kedua tidak
menimbulkan galat apa pun: volume lolos melampaui kontrak, diam-diam.
"""

from decimal import Decimal

import pytest

from repository.certificate_of_payment_repository import (
    JENIS_BOLEH_TANPA_PAGU,
    _tanpa_pagu,
    _volume_disepakati,
)

from certificate_of_payment_test import (  # noqa: F401  (fixture)
    BARIS_INDUK,
    CoP,
    _muatan,
    repo,
)


# --------------------------------------------------------------------------
# Siapa yang tanpa plafon
# --------------------------------------------------------------------------


def test_spk_d_bervolume_nol_tanpa_plafon():
    """Inilah bentuk SPK D yang dibuat layar sekarang: volume dikosongkan."""
    assert _tanpa_pagu("D", Decimal("0"), True) is True


def test_spk_d_bervolume_terisi_tetap_berplafon():
    """
    Volume yang DIISI adalah kesepakatan, dan harus dijaga.

    Pilihannya ada di tangan yang membuat SPK: dikosongkan berarti harga
    satuan, diisi berarti berplafon. Kalau yang terisi pun dibiarkan terbuka,
    kotak volumenya berhenti berarti apa-apa.
    """
    assert _tanpa_pagu("D", Decimal("2000"), True) is False


def test_spk_material_bervolume_nol_tetap_berplafon():
    """
    Pada SPK material, volume nol adalah DATA YANG KELIRU.

    Membukanya berarti menghapus penjagaan pagu justru di tempat yang paling
    membutuhkannya: baris beton bervolume nol akan menerima sertifikasi
    berapa pun, tanpa satu pun layar menyebutnya janggal.
    """
    for jenis in ("A", "B", "H", "6.4.1", "PO", "", None):
        assert _tanpa_pagu(jenis, Decimal("0"), True) is False, jenis


def test_jenis_tidak_peka_huruf_dan_spasi():
    """Kolomnya teks bebas; " d " dan "D" SPK yang sama."""
    assert _tanpa_pagu(" d ", Decimal("0"), True) is True


def test_volume_minus_ikut_terbuka():
    """
    `pagu - terpakai` dapat minus pada baris SPK D lama yang sudah terlanjur
    disertifikasi ketika plafonnya masih 1.

    Bila hanya nol yang dibuka, baris-baris itu tetap terkunci — dan justru
    merekalah yang sedang tidak dapat ditagih.
    """
    assert _tanpa_pagu("D", Decimal("-5"), True) is True


def test_hanya_d_yang_boleh():
    """Daftarnya sengaja berisi satu; melebarkannya keputusan tersendiri."""
    assert JENIS_BOLEH_TANPA_PAGU == frozenset({"D"})


# --------------------------------------------------------------------------
# Controller melewati pemeriksaannya
# --------------------------------------------------------------------------


def _pagu_tanpa_plafon(terpakai="0"):
    """Baris SPK D harga satuan, seperti yang dikembalikan `pagu()`."""
    return [
        {
            "purchaseOrderItemID": BARIS_INDUK,
            "purchaseOrderID": 5,
            "task": "Operator Drilling Rig",
            "unit": "m'",
            "itemID": None,
            "equipmentID": None,
            "keterangan": None,
            "komponen": "Upah borongan",
            "price": Decimal("35000"),
            "pagu": Decimal("0"),
            "terpakai": Decimal(terpakai),
            "sisa": Decimal("0") - Decimal(terpakai),
            "tanpaPagu": True,
        }
    ]


class TestTanpaPaguDiController:

    @pytest.mark.asyncio
    async def test_volume_besar_pada_baris_tanpa_plafon_diterima(self, repo):
        """
        2.000 m' pada baris bersisa NOL.

        Persis yang ditolak di lapangan sebelum ini: SPK 2.000 m' yang tidak
        dapat dibuatkan berita acara satu pun.
        """
        repo["pagu"] = _pagu_tanpa_plafon()
        hasil = await CoP.create(
            _muatan(2000), user_id=1, user_level=1,
            departments={"engineering"},
        )
        assert "error" not in hasil
        assert repo["items_disimpan"][0]["quantity"] == Decimal("2000")

    @pytest.mark.asyncio
    async def test_penagihan_kedua_tidak_tertahan_yang_pertama(self, repo):
        """
        Tanpa plafon berarti akumulasinya pun tidak menahan.

        Bulan kedua pada SPK upah bulanan tidak boleh ditolak hanya karena
        bulan pertama sudah disertifikasi.
        """
        repo["pagu"] = _pagu_tanpa_plafon(terpakai="2000")
        hasil = await CoP.create(
            _muatan(1500), user_id=1, user_level=1,
            departments={"engineering"},
        )
        assert "error" not in hasil

    @pytest.mark.asyncio
    async def test_volume_nol_tetap_ditolak(self, repo):
        """
        Yang dibuka PLAFONNYA, bukan aturan volume harus lebih dari nol.

        Berita acara bervolume nol tetap dapat disetujui dan ditagihkan, dan
        tidak ada satu pun layar yang akan menyebutnya janggal.
        """
        repo["pagu"] = _pagu_tanpa_plafon()
        hasil = await CoP.create(
            _muatan(0), user_id=1, user_level=1,
            departments={"engineering"},
        )
        assert hasil["status"] == 400
        assert repo["items_disimpan"] is None

    @pytest.mark.asyncio
    async def test_baris_berplafon_di_spk_yang_sama_tetap_dijaga(self, repo):
        """
        Satu SPK D dapat punya baris berplafon DAN tanpa plafon sekaligus —
        mis. upah bulanan tanpa plafon, mobilisasi 2 kali.

        Penandanya per BARIS. Bila ia terbaca per dokumen, membuka yang satu
        akan membuka yang lain diam-diam.
        """
        baris = _pagu_tanpa_plafon()
        baris[0]["tanpaPagu"] = False
        baris[0]["pagu"] = Decimal("2")
        baris[0]["sisa"] = Decimal("2")
        repo["pagu"] = baris
        hasil = await CoP.create(
            _muatan(3), user_id=1, user_level=1,
            departments={"engineering"},
        )
        assert hasil["status"] == 400


# --------------------------------------------------------------------------
# SPK LAMA — dikenali dari dokumennya, bukan dari angkanya
# --------------------------------------------------------------------------


def test_spk_d_lama_terbuka_walau_volumenya_satu():
    """
    INI YANG TERLEWAT pada perbaikan pertama, dan ini yang dilihat di lapangan.

    Formulir SPK D dulu mengirim `quantity: 1` pada SETIAP baris upah — ia
    tidak punya kotak volume sama sekali. Seluruh SPK D yang sudah terbit
    berisi angka itu.

    Perbaikan pertama hanya membuka baris bervolume NOL, yaitu bentuk yang
    ditulis formulir BARU. Akibatnya tidak ada satu pun SPK yang sudah terbit
    yang ikut terbuka: layar tetap menyebut "Volume SPK 1 hari", dan berita
    acara untuk pekerja yang sehari menyelesaikan 60 meter tetap ditolak.
    """
    assert _tanpa_pagu("D", Decimal("1"), volume_disepakati=False) is True


def test_spk_d_baru_bervolume_satu_TETAP_berplafon():
    """
    Satu yang DIKETIK orang adalah kesepakatan, dan harus ditegakkan.

    Inilah alasan penandanya ada pada dokumen dan bukan pada angkanya.
    Menebak "1 berarti penambal" akan membuat yang diketik berbeda dari yang
    ditegakkan begitu formulirnya punya kotak volume — tanpa galat apa pun.
    """
    assert _tanpa_pagu("D", Decimal("1"), volume_disepakati=True) is False


def test_spk_material_lama_TIDAK_ikut_terbuka():
    """
    Penanda yang hilang hanya berarti "formulir lama" pada jenis D.

    SPK material tidak pernah punya penambal itu; membukanya berarti
    menghapus penjagaan pagu pada dokumen yang justru paling membutuhkannya,
    dan seluruh SPK material lama sekaligus.
    """
    for jenis in ("A", "B", "H", "6.4.1"):
        assert _tanpa_pagu(jenis, Decimal("1"), volume_disepakati=False) is False


def test_penanda_dibaca_dari_customdata():
    """Bentuk dari dokumen sungguhan; yang tidak punya dibaca salah."""
    assert _volume_disepakati({"volumeDiisi": True}) is True
    assert _volume_disepakati({}) is False
    assert _volume_disepakati({"volumeDiisi": False}) is False
