"""
Pengujian Certificate of Payment.

CoP menyatakan berapa banyak pekerjaan sebuah SPK yang sudah terlaksana, dan
di atas pernyataan itulah tagihan disusun. Empat hal karena itu diuji di
sini, dan keempatnya menyentuh uang:

  1. AKUMULASI TIDAK MELAMPAUI PAGU — sewa 200 jam tidak boleh tertagih 205
     jam betapa pun banyak CoP yang dibuat;
  2. BARIS HARUS MILIK SPK-nya — pekerjaan SPK lain tidak dapat dititipkan;
  3. HARGA SELALU DARI SPK — angka yang dikirim layar diabaikan;
  4. LAPANGAN TIDAK MENERIMA HARGA — bukan menerimanya lalu menyembunyikan.

Ditambah alur tiga tangannya: yang mencatat bukan yang memeriksa, dan yang
memeriksa bukan yang menyetujui.

Repository ditiru — yang diuji keputusan controller, bukan MySQL-nya.
"""

from decimal import Decimal

import pytest

from controllers import certificate_of_payment_controller as modul
from controllers.certificate_of_payment_controller import (
    CertificateOfPaymentController as CoP,
)


# SPK contoh: satu baris sewa excavator 200 jam @ Rp 400.000.
BARIS_INDUK = 11
BARIS_ADENDUM = 12


def _pagu(terpakai_induk="0", pagu_induk="200", baris_adendum=None):
    """Susun keadaan pagu seperti yang dikembalikan repository."""
    baris = [
        {
            "purchaseOrderItemID": BARIS_INDUK,
            "purchaseOrderID": 5,
            "task": "Sewa excavator",
            "unit": "jam",
            "itemID": None,
            "equipmentID": 3,
            "keterangan": None,
            "price": Decimal("400000"),
            "pagu": Decimal(pagu_induk),
            "terpakai": Decimal(terpakai_induk),
            "sisa": Decimal(pagu_induk) - Decimal(terpakai_induk),
        }
    ]
    if baris_adendum is not None:
        baris.append(
            {
                "purchaseOrderItemID": BARIS_ADENDUM,
                "purchaseOrderID": 6,
                "task": "Sewa excavator",
                "unit": "jam",
                "itemID": None,
                "equipmentID": 3,
                "keterangan": "adendum 1",
                "price": Decimal("425000"),
                "pagu": Decimal(baris_adendum),
                "terpakai": Decimal("0"),
                "sisa": Decimal(baris_adendum),
            }
        )
    return baris


@pytest.fixture
def repo(monkeypatch):
    """
    Tiru repository CoP & purchase order.

    `keadaan["pagu"]` diubah tiap pengujian untuk menirukan CoP-CoP yang
    sudah ada sebelumnya.
    """
    keadaan = {
        "pagu": _pagu(),
        "spk": {
            "id": 5,
            "name": "013-SPK-MICZ-B",
            "projectName": "MICZ",
            "isApproved": True,
            "parentPurchaseOrderID": None,
            # Jenis B = penyewaan alat kerja, terbit sebagai SPK.
            "purchaseType": "B",
            "customData": None,
        },
        "dibuat": None,
        "items_disimpan": None,
        "cop": None,
    }

    async def _pagu_repo(po_id):
        return keadaan["pagu"]

    async def _spk(po_id):
        return dict(keadaan["spk"]) if keadaan["spk"] else {"error": "x", "status": 404}

    async def _nomor(po_id):
        return 1

    async def _create(data, items, user_id):
        keadaan["dibuat"] = dict(data)
        keadaan["items_disimpan"] = [dict(i) for i in items]
        return {"certificateOfPaymentID": 99, "name": data["name"], "number": 1}

    async def _get_by_id(cop_id):
        return dict(keadaan["cop"]) if keadaan["cop"] else {"error": "x", "status": 404}

    async def _set_checked(cop_id, checked, user_id):
        keadaan["set_checked"] = (cop_id, checked, user_id)
        return {"message": "ok"}

    async def _approve(cop_id, user_id):
        keadaan["approve"] = (cop_id, user_id)
        return {"message": "ok"}

    async def _ganti(cop_id, items, user_id):
        keadaan["items_disimpan"] = [dict(i) for i in items]
        return {"message": "ok"}

    async def _update_meta(cop_id, nilai, user_id):
        keadaan["meta"] = dict(nilai)
        return {"message": "ok"}

    monkeypatch.setattr(modul.CertificateOfPaymentRepository, "pagu", staticmethod(_pagu_repo))
    monkeypatch.setattr(modul.CertificateOfPaymentRepository, "nomor_berikut", staticmethod(_nomor))
    monkeypatch.setattr(modul.CertificateOfPaymentRepository, "create", staticmethod(_create))
    monkeypatch.setattr(modul.CertificateOfPaymentRepository, "get_by_id", staticmethod(_get_by_id))
    monkeypatch.setattr(modul.CertificateOfPaymentRepository, "set_checked", staticmethod(_set_checked))
    monkeypatch.setattr(modul.CertificateOfPaymentRepository, "approve", staticmethod(_approve))
    monkeypatch.setattr(modul.CertificateOfPaymentRepository, "ganti_items", staticmethod(_ganti))
    monkeypatch.setattr(modul.CertificateOfPaymentRepository, "update_meta", staticmethod(_update_meta))
    monkeypatch.setattr(modul.PurchaseOrderRepository, "get_by_id", staticmethod(_spk))
    return keadaan


def _muatan(qty, baris=BARIS_INDUK, **tambahan):
    return {
        "purchaseOrderID": 5,
        "date": "2026-08-24",
        "items": [{"purchaseOrderItemID": baris, "quantity": qty, **tambahan}],
    }


# =====================================================================
# 1. Pagu
# =====================================================================


class TestPagu:
    """Inti fitur: akumulasi lintas CoP tidak boleh melampaui SPK."""

    @pytest.mark.asyncio
    async def test_dalam_pagu_diterima(self, repo):
        hasil = await CoP.create(_muatan(40), user_id=1, user_level=1,
                                 departments={"engineering"})
        assert "error" not in hasil
        assert repo["items_disimpan"][0]["quantity"] == Decimal("40")

    @pytest.mark.asyncio
    async def test_pas_menghabiskan_pagu_diterima(self, repo):
        """Batasnya inklusif: 200 dari 200 masih sah."""
        repo["pagu"] = _pagu(terpakai_induk="155")
        hasil = await CoP.create(_muatan(45), user_id=1, user_level=1,
                                 departments={"engineering"})
        assert "error" not in hasil

    @pytest.mark.asyncio
    async def test_melebihi_pagu_ditolak(self, repo):
        """155 sudah terpakai; 50 lagi berarti 205 dari 200."""
        repo["pagu"] = _pagu(terpakai_induk="155")
        hasil = await CoP.create(_muatan(50), user_id=1, user_level=1,
                                 departments={"engineering"})
        assert hasil["status"] == 400
        assert repo["items_disimpan"] is None

    @pytest.mark.asyncio
    async def test_pesan_penolakan_menyebut_sisa_dan_adendum(self, repo):
        """
        Yang ditolak harus tahu berapa yang masih boleh, dan jalan keluarnya.
        Pesan "gagal" saja membuat orang mencoba angka lain satu per satu.
        """
        repo["pagu"] = _pagu(terpakai_induk="155")
        hasil = await CoP.create(_muatan(50), user_id=1, user_level=1,
                                 departments={"engineering"})
        pesan = str(hasil.get("error", ""))
        assert "45" in pesan
        assert "adendum" in pesan.lower()

    @pytest.mark.asyncio
    async def test_baris_kembar_dijumlahkan_dulu(self, repo):
        """
        Sepuluh baris @ 30 jam pada pagu 200 berarti 300 — harus ditolak.
        Diperiksa satu per satu, masing-masing muat dan semuanya lolos.
        """
        muatan = {
            "purchaseOrderID": 5,
            "date": "2026-08-24",
            "items": [
                {"purchaseOrderItemID": BARIS_INDUK, "quantity": 30}
                for _ in range(10)
            ],
        }
        hasil = await CoP.create(muatan, user_id=1, user_level=1,
                                 departments={"engineering"})
        assert hasil["status"] == 400
        assert repo["items_disimpan"] is None

    @pytest.mark.asyncio
    async def test_adendum_membuka_pagu_baru(self, repo):
        """
        Induk habis 200/200, tetapi adendum menambah 50 sebagai BARIS SENDIRI
        — dan barisnya punya harganya sendiri.
        """
        repo["pagu"] = _pagu(terpakai_induk="200", baris_adendum="50")

        habis = await CoP.create(_muatan(10), user_id=1, user_level=1,
                                 departments={"engineering"})
        assert habis["status"] == 400

        lanjut = await CoP.create(_muatan(50, baris=BARIS_ADENDUM), user_id=1,
                                  user_level=1, departments={"engineering"})
        assert "error" not in lanjut
        assert repo["items_disimpan"][0]["price"] == Decimal("425000")

    @pytest.mark.asyncio
    async def test_volume_nol_ditolak(self, repo):
        hasil = await CoP.create(_muatan(0), user_id=1, user_level=1,
                                 departments={"engineering"})
        assert hasil["status"] == 400

    @pytest.mark.asyncio
    async def test_volume_negatif_ditolak(self, repo):
        """Volume negatif akan MENGEMBALIKAN pagu — pintu belakang menambah pagu."""
        hasil = await CoP.create(_muatan(-20), user_id=1, user_level=1,
                                 departments={"engineering"})
        assert hasil["status"] == 400


# =====================================================================
# 2. Baris asing
# =====================================================================


class TestBarisAsing:
    @pytest.mark.asyncio
    async def test_baris_bukan_milik_spk_ditolak(self, repo):
        hasil = await CoP.create(_muatan(10, baris=999), user_id=1, user_level=1,
                                 departments={"engineering"})
        assert hasil["status"] == 400
        assert repo["items_disimpan"] is None

    @pytest.mark.asyncio
    async def test_tanpa_baris_ditolak(self, repo):
        hasil = await CoP.create(
            {"purchaseOrderID": 5, "date": "2026-08-24", "items": []},
            user_id=1, user_level=1, departments={"engineering"},
        )
        assert hasil["status"] == 400


# =====================================================================
# 3. Harga selalu dari SPK
# =====================================================================


class TestHargaDariSPK:
    @pytest.mark.asyncio
    async def test_harga_diambil_dari_spk(self, repo):
        await CoP.create(_muatan(10), user_id=1, user_level=1,
                         departments={"engineering"})
        baris = repo["items_disimpan"][0]
        assert baris["price"] == Decimal("400000")
        assert baris["amount"] == Decimal("4000000")

    @pytest.mark.asyncio
    async def test_harga_kiriman_layar_diabaikan(self, repo):
        """
        Muatan yang menyelipkan harganya sendiri tidak boleh mengubah apa pun.
        Inilah bedanya "tidak ditampilkan" dengan "tidak dipakai".
        """
        muatan = _muatan(10, price=1, amount=1)
        await CoP.create(muatan, user_id=1, user_level=1,
                         departments={"engineering"})
        baris = repo["items_disimpan"][0]
        assert baris["price"] == Decimal("400000")
        assert baris["amount"] == Decimal("4000000")


# =====================================================================
# 4. Lapangan tidak menerima harga
# =====================================================================


class TestPenyaringanNilai:
    def test_level_1_tidak_menerima_harga(self):
        data = {
            "id": 1,
            "name": "CoP-001",
            "total": 4000000,
            "items": [{"quantity": 10, "price": 400000, "amount": 4000000}],
        }
        keluar = CoP.saring_nilai(data, user_level=1)
        assert "total" not in keluar
        assert "price" not in keluar["items"][0]
        assert "amount" not in keluar["items"][0]
        # Yang bukan uang tetap utuh.
        assert keluar["items"][0]["quantity"] == 10
        assert keluar["name"] == "CoP-001"

    def test_level_2_menerima_harga(self):
        data = {"total": 4000000, "items": [{"price": 400000, "amount": 4000000}]}
        keluar = CoP.saring_nilai(data, user_level=2)
        assert keluar["total"] == 4000000
        assert keluar["items"][0]["price"] == 400000

    def test_daftar_ikut_disaring(self):
        """Jalan keluar lain tidak boleh terlewat — daftar pun disaring."""
        data = {"total": 1, "data": [{"total": 5, "items": [{"price": 9}]}]}
        keluar = CoP.saring_nilai(data, user_level=1)
        assert "total" not in keluar
        assert "total" not in keluar["data"][0]
        assert "price" not in keluar["data"][0]["items"][0]

    @pytest.mark.asyncio
    async def test_pagu_untuk_level_1_tanpa_harga(self, repo):
        keluar = await CoP.pagu_spk(5, user_level=1)
        assert "price" not in keluar[0]
        # Volume justru HARUS ada — itu yang dipakainya bekerja.
        assert keluar[0]["sisa"] == 200.0

    @pytest.mark.asyncio
    async def test_pagu_untuk_level_2_dengan_harga(self, repo):
        keluar = await CoP.pagu_spk(5, user_level=2)
        assert keluar[0]["price"] == 400000.0


# =====================================================================
# 5. Wewenang & tiga lapis
# =====================================================================


class TestWewenang:
    @pytest.mark.asyncio
    async def test_tanpa_divisi_engineering_ditolak(self, repo):
        hasil = await CoP.create(_muatan(10), user_id=1, user_level=1,
                                 departments={"procurement"})
        assert hasil["status"] == 403

    @pytest.mark.asyncio
    async def test_level_4_bebas_divisi(self, repo):
        hasil = await CoP.create(_muatan(10), user_id=1, user_level=4,
                                 departments=set())
        assert "error" not in hasil

    @pytest.mark.asyncio
    async def test_spk_belum_disetujui_ditolak(self, repo):
        repo["spk"]["isApproved"] = False
        hasil = await CoP.create(_muatan(10), user_id=1, user_level=1,
                                 departments={"engineering"})
        assert hasil["status"] == 400

    @pytest.mark.asyncio
    async def test_periksa_butuh_level_2(self, repo):
        repo["cop"] = {"id": 9, "createdBy": 7, "isChecked": False,
                       "isApproved": False, "checkedBy": None}
        hasil = await CoP.set_checked(9, True, user_id=1, user_level=1,
                                      departments={"engineering"})
        assert hasil["status"] == 403

    @pytest.mark.asyncio
    async def test_pembuat_tidak_memeriksa_sendiri(self, repo):
        repo["cop"] = {"id": 9, "createdBy": 7, "isChecked": False,
                       "isApproved": False, "checkedBy": None}
        hasil = await CoP.set_checked(9, True, user_id=7, user_level=2,
                                      departments={"engineering"})
        assert hasil["status"] == 403
        assert hasil["code"] == "SELF_APPROVAL_FORBIDDEN"

    @pytest.mark.asyncio
    async def test_periksa_oleh_orang_lain_diterima(self, repo):
        repo["cop"] = {"id": 9, "createdBy": 7, "isChecked": False,
                       "isApproved": False, "checkedBy": None}
        hasil = await CoP.set_checked(9, True, user_id=8, user_level=2,
                                      departments={"engineering"})
        assert "error" not in hasil
        assert repo["set_checked"] == (9, True, 8)

    @pytest.mark.asyncio
    async def test_setuju_butuh_level_3(self, repo):
        repo["cop"] = {"id": 9, "createdBy": 7, "isChecked": True,
                       "isApproved": False, "checkedBy": 8}
        hasil = await CoP.approve(9, user_id=8, user_level=2)
        assert hasil["status"] == 403

    @pytest.mark.asyncio
    async def test_belum_diperiksa_tidak_dapat_disetujui(self, repo):
        repo["cop"] = {"id": 9, "createdBy": 7, "isChecked": False,
                       "isApproved": False, "checkedBy": None}
        hasil = await CoP.approve(9, user_id=3, user_level=3)
        assert hasil["status"] == 400

    @pytest.mark.asyncio
    async def test_pemeriksa_tidak_menyetujui_periksaannya(self, repo):
        repo["cop"] = {"id": 9, "createdBy": 7, "isChecked": True,
                       "isApproved": False, "checkedBy": 3}
        hasil = await CoP.approve(9, user_id=3, user_level=3)
        assert hasil["status"] == 403
        assert hasil["code"] == "PO_CHECKER_IS_APPROVER"

    @pytest.mark.asyncio
    async def test_alur_lengkap_tiga_tangan(self, repo):
        """Dibuat orang 1, diperiksa orang 2, disetujui orang 3."""
        buat = await CoP.create(_muatan(40), user_id=1, user_level=1,
                                departments={"engineering"})
        assert "error" not in buat

        repo["cop"] = {"id": 99, "createdBy": 1, "isChecked": False,
                       "isApproved": False, "checkedBy": None}
        periksa = await CoP.set_checked(99, True, user_id=2, user_level=2,
                                        departments={"engineering"})
        assert "error" not in periksa

        repo["cop"] = {"id": 99, "createdBy": 1, "isChecked": True,
                       "isApproved": False, "checkedBy": 2}
        setuju = await CoP.approve(99, user_id=3, user_level=3)
        assert "error" not in setuju
        assert repo["approve"] == (99, 3)

    @pytest.mark.asyncio
    async def test_sudah_disetujui_tidak_disetujui_ulang(self, repo):
        repo["cop"] = {"id": 9, "createdBy": 7, "isChecked": True,
                       "isApproved": True, "checkedBy": 8}
        hasil = await CoP.approve(9, user_id=3, user_level=3)
        assert hasil["status"] == 409


# =====================================================================
# 6. Sunting
# =====================================================================


class TestSunting:
    @pytest.mark.asyncio
    async def test_sudah_diperiksa_tidak_dapat_diubah(self, repo):
        repo["cop"] = {"id": 9, "createdBy": 1, "purchaseOrderID": 5,
                       "isChecked": True, "items": []}
        hasil = await CoP.update(9, {"note": "x"}, user_id=1, user_level=1,
                                 departments={"engineering"})
        assert hasil["status"] == 409

    @pytest.mark.asyncio
    async def test_bukan_pembuat_level_rendah_ditolak(self, repo):
        repo["cop"] = {"id": 9, "createdBy": 1, "purchaseOrderID": 5,
                       "isChecked": False, "items": []}
        hasil = await CoP.update(9, {"note": "x"}, user_id=2, user_level=1,
                                 departments={"engineering"})
        assert hasil["status"] == 403

    @pytest.mark.asyncio
    async def test_volume_sendiri_tidak_dihitung_dua_kali(self, repo):
        """
        CoP ini sudah memakai 45 dari sisa 45. Menyuntingnya menjadi 45 lagi
        harus DITERIMA — volumenya sendiri bukan pemakaian orang lain.
        Tanpa pengecualian ini, membuka lalu menyimpan tanpa mengubah apa pun
        akan ditolak.
        """
        repo["pagu"] = _pagu(terpakai_induk="200")
        repo["cop"] = {
            "id": 9, "createdBy": 1, "purchaseOrderID": 5, "isChecked": False,
            "items": [{"purchaseOrderItemID": BARIS_INDUK, "quantity": Decimal("45")}],
        }
        hasil = await CoP.update(
            9,
            {"items": [{"purchaseOrderItemID": BARIS_INDUK, "quantity": 45}]},
            user_id=1, user_level=1, departments={"engineering"},
        )
        assert "error" not in hasil

    @pytest.mark.asyncio
    async def test_sunting_melebihi_pagu_tetap_ditolak(self, repo):
        repo["pagu"] = _pagu(terpakai_induk="200")
        repo["cop"] = {
            "id": 9, "createdBy": 1, "purchaseOrderID": 5, "isChecked": False,
            "items": [{"purchaseOrderItemID": BARIS_INDUK, "quantity": Decimal("45")}],
        }
        hasil = await CoP.update(
            9,
            {"items": [{"purchaseOrderItemID": BARIS_INDUK, "quantity": 60}]},
            user_id=1, user_level=1, departments={"engineering"},
        )
        assert hasil["status"] == 400


# =====================================================================
# 7. Hapus
# =====================================================================


class TestHapus:
    @pytest.mark.asyncio
    async def test_disetujui_tidak_dihapus_di_bawah_level_4(self, repo):
        repo["cop"] = {"id": 9, "createdBy": 1, "isApproved": True}
        hasil = await CoP.delete(9, user_id=1, user_level=3)
        assert hasil["status"] == 403

    @pytest.mark.asyncio
    async def test_level_4_boleh_menghapus_yang_disetujui(self, repo, monkeypatch):
        repo["cop"] = {"id": 9, "createdBy": 1, "isApproved": True}

        async def _hapus(cop_id, user_id):
            return {"message": "ok"}

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "soft_delete", staticmethod(_hapus)
        )
        hasil = await CoP.delete(9, user_id=4, user_level=4)
        assert "error" not in hasil


# =====================================================================
# 8. Hanya SPK, bukan purchase order pembelian
# =====================================================================


class TestHanyaSPK:
    """
    CoP mensertifikasi PEKERJAAN yang terlaksana bertahap — itu yang
    diperintahkan surat perintah kerja. Purchase order pembelian barang
    diterima sekali; progres mingguan atasnya tidak berarti apa pun, dan
    membiarkannya membuat dua jenis dokumen yang alurnya berbeda bercampur.
    """

    @pytest.mark.asyncio
    async def test_purchase_order_pembelian_ditolak(self, repo):
        # Jenis G = pengadaan barang, terbit sebagai PURCHASE ORDER.
        repo["spk"]["purchaseType"] = "G"
        repo["spk"]["name"] = "013-PO-MICZ-G"
        hasil = await CoP.create(_muatan(10), user_id=1, user_level=1,
                                 departments={"engineering"})
        assert hasil["status"] == 400
        assert "SPK" in hasil["error"]
        assert repo["items_disimpan"] is None

    @pytest.mark.asyncio
    async def test_pagu_purchase_order_pembelian_ditolak(self, repo):
        """Ditolak SEBELUM layarnya sempat memuat baris yang salah."""
        repo["spk"]["purchaseType"] = "G"
        hasil = await CoP.pagu_spk(5, user_level=1)
        assert isinstance(hasil, dict)
        assert hasil["status"] == 400

    @pytest.mark.asyncio
    async def test_jenis_spk_diterima(self, repo):
        for jenis in ("A", "B", "D", "H", "H1", "6.4.1"):
            repo["spk"]["purchaseType"] = jenis
            repo["items_disimpan"] = None
            hasil = await CoP.create(_muatan(10), user_id=1, user_level=1,
                                     departments={"engineering"})
            assert "error" not in hasil, f"jenis {jenis} seharusnya SPK"

    @pytest.mark.asyncio
    async def test_po_f_jasa_uji_adalah_spk(self, repo):
        """
        PO-F bentuknya bergantung isian: jasa pengujian terbit sebagai SPK,
        pengadaan materialnya sebagai PO. Keduanya harus dibedakan dengan
        benar — inilah alasan jenis dokumen tidak boleh ditebak dari teks
        namanya.
        """
        repo["spk"]["purchaseType"] = "F"
        repo["spk"]["customData"] = {"materialType": "ujitekan"}
        hasil = await CoP.create(_muatan(10), user_id=1, user_level=1,
                                 departments={"engineering"})
        assert "error" not in hasil

    @pytest.mark.asyncio
    async def test_po_f_material_bukan_spk(self, repo):
        repo["spk"]["purchaseType"] = "F"
        repo["spk"]["customData"] = {"materialType": "beton"}
        hasil = await CoP.create(_muatan(10), user_id=1, user_level=1,
                                 departments={"engineering"})
        assert hasil["status"] == 400

    @pytest.mark.asyncio
    async def test_custom_data_berupa_teks_json_tetap_terbaca(self, repo):
        """Basis data mengembalikan JSON sebagai teks pada sebagian jalur."""
        repo["spk"]["purchaseType"] = "F"
        repo["spk"]["customData"] = '{"materialType": "ujitanah"}'
        hasil = await CoP.create(_muatan(10), user_id=1, user_level=1,
                                 departments={"engineering"})
        assert "error" not in hasil


# =====================================================================
# 9. Potongan & tambahan
# =====================================================================


@pytest.fixture
def repo_penyesuaian(repo, monkeypatch):
    """Tambahkan tiruan penyimpanan penyesuaian di atas fixture `repo`."""

    async def _ganti(cop_id, penyesuaian, user_id):
        repo["penyesuaian"] = [dict(p) for p in penyesuaian]
        kotor = Decimal(str(repo["cop"].get("grossAmount") or 0))
        potongan = sum(
            (p["amount"] for p in penyesuaian if p["kind"] == "deduction"),
            Decimal("0"),
        )
        tambahan = sum(
            (p["amount"] for p in penyesuaian if p["kind"] == "addition"),
            Decimal("0"),
        )
        return {
            "grossAmount": kotor,
            "deductionTotal": potongan,
            "additionTotal": tambahan,
            "netAmount": kotor - potongan + tambahan,
        }

    monkeypatch.setattr(
        modul.CertificateOfPaymentRepository,
        "ganti_penyesuaian",
        staticmethod(_ganti),
    )
    repo["penyesuaian"] = None
    repo["cop"] = {
        "id": 9,
        "createdBy": 1,
        "isChecked": True,
        "isApproved": False,
        "checkedBy": 2,
        "grossAmount": Decimal("10000000"),
    }
    return repo


def _pot(kategori="uang_muka", nominal=1000000, **tambahan):
    return {"kind": "deduction", "category": kategori, "amount": nominal, **tambahan}


def _tam(kategori="biaya_luar_kontrak", nominal=500000, **tambahan):
    return {"kind": "addition", "category": kategori, "amount": nominal, **tambahan}


class TestPenyesuaian:
    """
    Potongan mengurangi DPP, tambahan menambahnya, dan keduanya hanya boleh
    disentuh pemeriksa.
    """

    @pytest.mark.asyncio
    async def test_potongan_mengurangi_nilai_bersih(self, repo_penyesuaian):
        hasil = await CoP.set_penyesuaian(
            9, [_pot(nominal=2000000)], user_id=2, user_level=2,
            departments={"engineering"},
        )
        assert "error" not in hasil
        assert hasil["deductionTotal"] == 2000000
        assert hasil["netAmount"] == 8000000

    @pytest.mark.asyncio
    async def test_tambahan_menambah_nilai_bersih(self, repo_penyesuaian):
        hasil = await CoP.set_penyesuaian(
            9, [_tam(nominal=500000)], user_id=2, user_level=2,
            departments={"engineering"},
        )
        assert hasil["additionTotal"] == 500000
        assert hasil["netAmount"] == 10500000

    @pytest.mark.asyncio
    async def test_potongan_dan_tambahan_bersamaan(self, repo_penyesuaian):
        hasil = await CoP.set_penyesuaian(
            9,
            [
                _pot("uang_muka", 2000000),
                _pot("retensi", 500000),
                _tam("biaya_luar_kontrak", 300000),
            ],
            user_id=2, user_level=2, departments={"engineering"},
        )
        assert hasil["deductionTotal"] == 2500000
        assert hasil["additionTotal"] == 300000
        assert hasil["netAmount"] == 7800000

    @pytest.mark.asyncio
    async def test_level_1_tidak_boleh_mengisi(self, repo_penyesuaian):
        """Orang lapangan tidak pernah menyentuh rupiah — termasuk di sini."""
        hasil = await CoP.set_penyesuaian(
            9, [_pot()], user_id=1, user_level=1, departments={"engineering"},
        )
        assert hasil["status"] == 403
        assert repo_penyesuaian["penyesuaian"] is None

    @pytest.mark.asyncio
    async def test_terkunci_setelah_disetujui(self, repo_penyesuaian):
        repo_penyesuaian["cop"]["isApproved"] = True
        hasil = await CoP.set_penyesuaian(
            9, [_pot()], user_id=2, user_level=2, departments={"engineering"},
        )
        assert hasil["status"] == 409
        assert repo_penyesuaian["penyesuaian"] is None

    @pytest.mark.asyncio
    async def test_nilai_bersih_negatif_ditolak(self, repo_penyesuaian):
        """Potongan melebihi nilai pekerjaan berarti pemasok berutang — bukan progres."""
        hasil = await CoP.set_penyesuaian(
            9, [_pot(nominal=12000000)], user_id=2, user_level=2,
            departments={"engineering"},
        )
        assert hasil["status"] == 400
        assert repo_penyesuaian["penyesuaian"] is None

    @pytest.mark.asyncio
    async def test_bersih_nol_masih_boleh(self, repo_penyesuaian):
        """Batasnya inklusif: potongan yang PAS menghabiskan nilainya sah."""
        hasil = await CoP.set_penyesuaian(
            9, [_pot(nominal=10000000)], user_id=2, user_level=2,
            departments={"engineering"},
        )
        assert "error" not in hasil
        assert hasil["netAmount"] == 0

    @pytest.mark.asyncio
    async def test_kategori_karangan_ditolak(self, repo_penyesuaian):
        hasil = await CoP.set_penyesuaian(
            9, [_pot("potongan_rahasia")], user_id=2, user_level=2,
            departments={"engineering"},
        )
        assert hasil["status"] == 400

    @pytest.mark.asyncio
    async def test_kategori_potongan_tidak_berlaku_untuk_tambahan(
        self, repo_penyesuaian
    ):
        """`retensi` hanya berarti sebagai potongan; sebagai tambahan ia omong kosong."""
        hasil = await CoP.set_penyesuaian(
            9, [_tam("retensi")], user_id=2, user_level=2,
            departments={"engineering"},
        )
        assert hasil["status"] == 400

    @pytest.mark.asyncio
    async def test_lain_lain_wajib_berlabel(self, repo_penyesuaian):
        hasil = await CoP.set_penyesuaian(
            9, [_pot("lain_lain")], user_id=2, user_level=2,
            departments={"engineering"},
        )
        assert hasil["status"] == 400

    @pytest.mark.asyncio
    async def test_lain_lain_berlabel_diterima(self, repo_penyesuaian):
        hasil = await CoP.set_penyesuaian(
            9, [_pot("lain_lain", label="Potongan material dipinjam")],
            user_id=2, user_level=2, departments={"engineering"},
        )
        assert "error" not in hasil
        assert repo_penyesuaian["penyesuaian"][0]["label"] == "Potongan material dipinjam"

    @pytest.mark.asyncio
    async def test_nominal_negatif_ditolak(self, repo_penyesuaian):
        """
        Tanda ditentukan `kind`, bukan nilainya. Nominal minus pada sebuah
        potongan justru MENAMBAH — pintu belakang yang tidak terlihat pada
        laporan mana pun.
        """
        hasil = await CoP.set_penyesuaian(
            9, [_pot(nominal=-5000000)], user_id=2, user_level=2,
            departments={"engineering"},
        )
        assert hasil["status"] == 400

    @pytest.mark.asyncio
    async def test_nominal_nol_ditolak(self, repo_penyesuaian):
        hasil = await CoP.set_penyesuaian(
            9, [_pot(nominal=0)], user_id=2, user_level=2,
            departments={"engineering"},
        )
        assert hasil["status"] == 400

    @pytest.mark.asyncio
    async def test_daftar_kosong_mengosongkan_penyesuaian(self, repo_penyesuaian):
        """Mengirim daftar kosong berarti mencabut seluruhnya — bukan galat."""
        hasil = await CoP.set_penyesuaian(
            9, [], user_id=2, user_level=2, departments={"engineering"},
        )
        assert "error" not in hasil
        assert hasil["netAmount"] == 10000000
        assert repo_penyesuaian["penyesuaian"] == []


class TestPenyaringanPenyesuaian:
    """Level 1 tidak menerima ringkasan nilai MAUPUN baris penyesuaiannya."""

    def test_level_1_tidak_menerima_ringkasan_dan_penyesuaian(self):
        data = {
            "id": 1,
            "name": "CoP-001",
            "grossAmount": 10000000,
            "deductionTotal": 2000000,
            "additionTotal": 0,
            "netAmount": 8000000,
            "adjustments": [
                {"kind": "deduction", "category": "uang_muka", "amount": 2000000},
            ],
            "items": [{"quantity": 10, "price": 400000, "amount": 4000000}],
        }
        keluar = CoP.saring_nilai(data, user_level=1)
        for k in ("grossAmount", "deductionTotal", "additionTotal", "netAmount"):
            assert k not in keluar
        # Barisnya dibuang SELURUHNYA: "Potongan uang muka" tanpa angka pun
        # sudah menceritakan susunan kesepakatan dengan pemasok.
        assert "adjustments" not in keluar
        assert keluar["items"][0]["quantity"] == 10

    def test_level_2_menerima_seluruhnya(self):
        data = {
            "grossAmount": 10000000,
            "netAmount": 8000000,
            "adjustments": [{"kind": "deduction", "amount": 2000000}],
        }
        keluar = CoP.saring_nilai(data, user_level=2)
        assert keluar["netAmount"] == 8000000
        assert len(keluar["adjustments"]) == 1
