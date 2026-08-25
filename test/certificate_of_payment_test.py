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
from repository.certificate_of_payment_repository import (
    CertificateOfPaymentRepository as Repo,
)
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
        # Nama TIDAK datang dari controller: ia disusun di dalam transaksi
        # penyimpanan, bersama nomor dokumennya. Tiruan ini menirukan itu —
        # kalau tidak, tesnya akan lulus atas kontrak yang sudah tidak
        # berlaku.
        nama = data.get("name") or Repo.susun_nama(
            1, data.get("projectName") or "", data.get("date")
        )
        return {"certificateOfPaymentID": 99, "name": nama, "number": 1}

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
    # Periode ikut disertakan: ia WAJIB sejak berita acara progres tanpa
    # rentang tanggal dinyatakan tidak dapat dibaca.
    return {
        "purchaseOrderID": 5,
        "date": "2026-08-24",
        "periodStart": "2026-08-18",
        "periodEnd": "2026-08-24",
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
            "periodStart": "2026-08-18",
            "periodEnd": "2026-08-24",
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
            {"purchaseOrderID": 5, "date": "2026-08-24",
             "periodStart": "2026-08-18", "periodEnd": "2026-08-24",
             "items": []},
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
    async def test_jenis_tanpa_cop_dikecualikan(self, repo):
        """
        A tidak ditagihkan bertahap; D penagihannya lewat pembuat faktur
        yang sudah ada. Keduanya memang terbit sebagai SPK, tetapi bukan
        SPK yang memakai berita acara progres.
        """
        for jenis in ("A", "D"):
            repo["spk"]["purchaseType"] = jenis
            hasil = await CoP.create(_muatan(10), user_id=1, user_level=1,
                                     departments={"engineering"})
            assert hasil["status"] == 400

    @pytest.mark.asyncio
    async def test_jenis_spk_diterima(self, repo):
        for jenis in ("B", "H", "H1", "6.4.1", "6.4.2"):
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
        "purchaseOrderID": 5,
        "createdBy": 1,
        "isChecked": True,
        "isApproved": False,
        "checkedBy": 2,
        "grossAmount": Decimal("10000000"),
    }

    # SPK contoh TANPA uang muka & retensi, supaya pengujian dasar
    # penyesuaian tidak ikut menguji pagunya. Pagu diuji terpisah di
    # `TestPaguUangMukaRetensi`.
    async def _nilai_kontrak(po_id):
        return repo.get("nilaiKontrak", Decimal("0"))

    async def _akumulasi(po_id, kecuali_cop_id=None):
        return repo.get("akumulasi", {})

    monkeypatch.setattr(
        modul.CertificateOfPaymentRepository,
        "nilai_kontrak",
        staticmethod(_nilai_kontrak),
    )
    monkeypatch.setattr(
        modul.CertificateOfPaymentRepository,
        "akumulasi_penyesuaian",
        staticmethod(_akumulasi),
    )
    repo["spk"]["dpPercentage"] = 0.0
    repo["spk"]["retentionPercentage"] = 0.0
    repo["spk"]["pphPercentage"] = 0.0
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


# =====================================================================
# 10. Data pencetakan (CoP + BAP)
# =====================================================================


@pytest.fixture
def repo_cetak(repo, monkeypatch):
    """
    SPK dua baris, sudah ada CoP nomor 1, dan yang dicetak nomor 2.

    Angka contohnya sengaja diambil dari lembar Excel yang selama ini
    dipakai (proyek R501) supaya hasil hitungnya dapat dibandingkan langsung
    dengan dokumen yang sudah pernah terbit.
    """
    baris = [
        {"id": 11, "task": "Beton f'c 12.5 MPa", "unit": "m3",
         "quantity": Decimal("4850"), "price": Decimal("845000"),
         "remarks_1": None, "purchaseOrderID": 5, "addendumNumber": None},
        {"id": 12, "task": "Beton f'c 30 MPa", "unit": "m3",
         "quantity": Decimal("7500"), "price": Decimal("925000"),
         "remarks_1": None, "purchaseOrderID": 5, "addendumNumber": None},
    ]

    async def _baris_kontrak(po_id):
        return [dict(b) for b in baris]

    async def _sebelumnya(po_id, nomor):
        return repo.get("sebelumnya", {})

    async def _riwayat(po_id, nomor):
        return repo.get("riwayat", [])

    monkeypatch.setattr(
        modul.CertificateOfPaymentRepository, "baris_kontrak", staticmethod(_baris_kontrak)
    )
    monkeypatch.setattr(
        modul.CertificateOfPaymentRepository, "cop_sebelumnya", staticmethod(_sebelumnya)
    )
    monkeypatch.setattr(
        modul.CertificateOfPaymentRepository,
        "riwayat_pembayaran",
        staticmethod(_riwayat),
    )

    repo["spk"]["ppn"] = Decimal("11")
    repo["spk"]["dpPercentage"] = 20.0
    repo["spk"]["retentionPercentage"] = 5.0
    repo["spk"]["pphPercentage"] = 2.0
    repo["spk"]["supplierName"] = "PT. Adhimix RMC Indonesia"
    repo["sebelumnya"] = {}
    repo["riwayat"] = []
    repo["cop"] = {
        "id": 9, "name": "008-PO-R501-F/CoP-001", "number": 1,
        "purchaseOrderID": 5, "projectName": "R501",
        "date": "2026-08-11", "periodStart": None, "periodEnd": None,
        "note": None, "createdBy": 1, "createdByName": "Budi",
        "checkedByName": "Sari", "approvedByName": "Daniel",
        "checkedAt": None, "approvedAt": None,
        "isChecked": True, "isApproved": True,
        "grossAmount": Decimal("52390000"),
        "deductionTotal": Decimal("0"),
        "additionTotal": Decimal("0"),
        "netAmount": Decimal("52390000"),
        "items": [{"purchaseOrderItemID": 11, "quantity": Decimal("62"),
                   "remarks": None}],
        "adjustments": [],
    }
    return repo


class TestDataCetak:
    @pytest.mark.asyncio
    async def test_nilai_kontrak_dijumlah_dari_baris(self, repo_cetak):
        hasil = await CoP.data_cetak(9, user_level=2)
        # 4850 x 845.000 + 7500 x 925.000
        assert hasil["kontrak"]["total"] == 11_035_750_000

    @pytest.mark.asyncio
    async def test_bobot_baris_berjumlah_satu(self, repo_cetak):
        """Bobot adalah porsi nilai tiap baris; seluruhnya harus 100%."""
        hasil = await CoP.data_cetak(9, user_level=2)
        total = sum(b["bobot"] for b in hasil["bap"])
        assert abs(total - 1.0) < 1e-9

    @pytest.mark.asyncio
    async def test_bobot_progres_cocok_dengan_lembar_lama(self, repo_cetak):
        """
        62 m3 dari 4850 m3 pada baris berbobot 37,136% menghasilkan
        0,4747298552431869% — angka yang sama persis dengan lembar Excel
        yang sudah pernah terbit untuk proyek ini.
        """
        hasil = await CoP.data_cetak(9, user_level=2)
        assert abs(hasil["nilai"]["persenProgres"] - 0.004747298552431869) < 1e-15

    @pytest.mark.asyncio
    async def test_ppn_mengikuti_tarif_spk(self, repo_cetak):
        hasil = await CoP.data_cetak(9, user_level=2)
        # Dibandingkan dengan angka BULAT, bukan hasil perkalian float.
        #
        # `52_390_000 * 1.11` dalam float menghasilkan 58152900.00000001;
        # yang dihitung controller lewat Decimal menghasilkan 58152900 tepat.
        # Menuliskan ekspresi float sebagai harapan justru membuat pengujian
        # menuntut jawaban yang KELIRU.
        assert hasil["nilai"]["ppn"] == 5_762_900
        assert hasil["nilai"]["totalDibayar"] == 58_152_900

    @pytest.mark.asyncio
    async def test_tarif_ppn_lama_tidak_dipaksa_sebelas_persen(self, repo_cetak):
        """Dokumen ber-PPN 10% harus tercetak ulang dengan 10%, bukan 11%."""
        repo_cetak["spk"]["ppn"] = Decimal("10")
        hasil = await CoP.data_cetak(9, user_level=2)
        assert hasil["nilai"]["ppn"] == 5_239_000

    @pytest.mark.asyncio
    async def test_volume_sebelumnya_masuk_kolomnya(self, repo_cetak):
        repo_cetak["sebelumnya"] = {11: Decimal("62")}
        repo_cetak["cop"]["number"] = 2
        hasil = await CoP.data_cetak(9, user_level=2)
        b = hasil["bap"][0]
        assert b["volumeSebelumnya"] == 62
        assert b["volumePeriodeIni"] == 62
        assert b["volumeAkumulatif"] == 124

    @pytest.mark.asyncio
    async def test_baris_tak_dikerjakan_bernilai_nol(self, repo_cetak):
        """Baris yang tidak disentuh periode ini tetap TAMPIL, bernilai nol."""
        hasil = await CoP.data_cetak(9, user_level=2)
        assert len(hasil["bap"]) == 2
        assert hasil["bap"][1]["volumePeriodeIni"] == 0
        assert hasil["bap"][1]["bobotSaatIni"] == 0

    @pytest.mark.asyncio
    async def test_persentase_penyesuaian_dihitung_dari_kotor(self, repo_cetak):
        repo_cetak["cop"]["adjustments"] = [
            {"kind": "deduction", "category": "uang_muka", "label": None,
             "amount": Decimal("10478000")},
        ]
        hasil = await CoP.data_cetak(9, user_level=2)
        # 10.478.000 / 52.390.000 = 20%
        assert abs(hasil["penyesuaian"][0]["persenDariKotor"] - 0.20) < 1e-12

    @pytest.mark.asyncio
    async def test_syarat_kontrak_ikut_tercetak(self, repo_cetak):
        hasil = await CoP.data_cetak(9, user_level=2)
        assert hasil["spk"]["dpPercentage"] == 20.0
        assert hasil["spk"]["retentionPercentage"] == 5.0

    @pytest.mark.asyncio
    async def test_level_1_tidak_boleh_mengunduh(self, repo_cetak):
        """Lembar ini memuat harga satuan dan nilai kontrak."""
        hasil = await CoP.data_cetak(9, user_level=1)
        assert hasil["status"] == 403

    @pytest.mark.asyncio
    async def test_pembagian_nol_tidak_meledak(self, repo_cetak, monkeypatch):
        """SPK bernilai nol tidak boleh menggagalkan pencetakan."""

        async def _kosong(po_id):
            return [
                {"id": 11, "task": "Gratis", "unit": "ls",
                 "quantity": Decimal("0"), "price": Decimal("0"),
                 "remarks_1": None, "purchaseOrderID": 5, "addendumNumber": None},
            ]

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository,
            "baris_kontrak",
            staticmethod(_kosong),
        )
        hasil = await CoP.data_cetak(9, user_level=2)
        assert "error" not in hasil
        assert hasil["bap"][0]["bobot"] == 0


class TestJenisATertutupSemuaJalur:
    """
    Jenis A tidak memakai CoP & BAP sama sekali.

    Diuji pada SETIAP pintu masuk, bukan satu saja: satu jalur yang lupa
    dijaga sudah cukup membuat aturannya tidak berlaku — dan yang menemukan
    celahnya biasanya bukan yang menulis kodenya.
    """

    @pytest.mark.asyncio
    async def test_tidak_muncul_di_daftar_pilihan(self, repo, monkeypatch):
        async def _kandidat(project_name=None, keyword=None, batas=50):
            return [
                {"id": 1, "name": "001-SPK-X-A", "projectName": "X",
                 "purchaseType": "A", "customData": None, "date": None,
                 "dpp": 100, "supplierName": "PT A"},
                {"id": 3, "name": "003-SPK-X-D", "projectName": "X",
                 "purchaseType": "D", "customData": None, "date": None,
                 "dpp": 300, "supplierName": "PT D"},
                {"id": 2, "name": "002-SPK-X-B", "projectName": "X",
                 "purchaseType": "B", "customData": None, "date": None,
                 "dpp": 200, "supplierName": "PT B"},
            ]

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository,
            "spk_kandidat",
            staticmethod(_kandidat),
        )
        hasil = await CoP.spk_kandidat(user_level=2)
        assert [s["purchaseType"] for s in hasil] == ["B"]

    @pytest.mark.asyncio
    async def test_tidak_bisa_dibuat(self, repo):
        for jenis in ("A", "D"):
            repo["spk"]["purchaseType"] = jenis
            hasil = await CoP.create(_muatan(10), user_id=1, user_level=1,
                                     departments={"engineering"})
            assert hasil["status"] == 400, jenis

    @pytest.mark.asyncio
    async def test_pagunya_tidak_bisa_dibuka(self, repo):
        repo["spk"]["purchaseType"] = "D"
        hasil = await CoP.pagu_spk(5, user_level=2)
        assert isinstance(hasil, dict) and hasil["status"] == 400

    @pytest.mark.asyncio
    async def test_tidak_bisa_dicetak(self, repo_cetak):
        """Termasuk CoP lama yang terlanjur tersimpan sebelum aturan ini ada."""
        repo_cetak["spk"]["purchaseType"] = "A"
        hasil = await CoP.data_cetak(9, user_level=2)
        assert hasil["status"] == 400
        repo_cetak["spk"]["purchaseType"] = "D"
        hasil = await CoP.data_cetak(9, user_level=2)
        assert hasil["status"] == 400


# =====================================================================
# 11. Lapangan tidak boleh tahu harga — disisir menyeluruh
# =====================================================================


#: Nama kolom yang MEMBAWA nilai uang, di mana pun ia muncul.
#:
#: Dipakai penyisir di bawah. Daftar ini sengaja berlebih: `dpp`, `total`,
#: dan `saran*` belum tentu ada hari ini, tetapi bila kelak ditambahkan dan
#: lupa disaring, pengujian ini yang menemukannya — bukan orang lapangan
#: yang membuka perkakas pengembang.
KOLOM_UANG = {
    "price", "amount", "dpp", "total", "totalAmount",
    "grossAmount", "deductionTotal", "additionTotal", "netAmount",
    "hargaSatuan", "saranPph", "saranUangMuka", "saranRetensi",
    "pphPercentage", "dpPercentage", "retentionPercentage",
}


def _sisir_uang(simpul, jalur="") -> list[str]:
    """Telusuri SELURUH jawaban; kembalikan jalur tiap kolom uang yang lolos."""
    temuan: list[str] = []
    if isinstance(simpul, dict):
        for k, v in simpul.items():
            j = f"{jalur}.{k}" if jalur else k
            if k in KOLOM_UANG:
                temuan.append(j)
            temuan += _sisir_uang(v, j)
    elif isinstance(simpul, list):
        for i, v in enumerate(simpul):
            temuan += _sisir_uang(v, f"{jalur}[{i}]")
    return temuan


class TestLapanganTidakTahuHarga:
    """
    Aturan yang paling sering ditanyakan pemilik, dan paling mudah bocor:
    orang lapangan mengisi VOLUME, dan hanya volume.

    Diuji dengan MENYISIR seluruh jawaban, bukan memeriksa beberapa kolom
    yang diingat. Kolom baru yang lupa disaring akan tertangkap di sini.
    """

    @pytest.mark.asyncio
    async def test_pagu_bersih_dari_uang(self, repo):
        hasil = await CoP.pagu_spk(5, user_level=1)
        assert _sisir_uang(hasil) == []
        # Volume justru HARUS ada — itu bahan kerjanya.
        assert hasil[0]["sisa"] == 200.0
        assert hasil[0]["pagu"] == 200.0

    @pytest.mark.asyncio
    async def test_detail_bersih_dari_uang(self, repo, monkeypatch):
        repo["cop"] = {
            "id": 9, "name": "CoP-001", "purchaseOrderID": 5,
            "createdBy": 1, "isChecked": True, "isApproved": False,
            "grossAmount": Decimal("52390000"),
            "deductionTotal": Decimal("1000000"),
            "additionTotal": Decimal("0"),
            "netAmount": Decimal("51390000"),
            "items": [{"purchaseOrderItemID": 11, "quantity": Decimal("62"),
                       "price": Decimal("845000"), "amount": Decimal("52390000"),
                       "unit": "m3", "task": "Beton"}],
            "adjustments": [{"kind": "deduction", "category": "uang_muka",
                             "amount": Decimal("1000000")}],
        }
        hasil = await CoP.get_by_id(9, user_level=1)
        assert _sisir_uang(hasil) == []
        # Yang tersisa tetap berguna: volume, satuan, dan nama pekerjaannya.
        assert hasil["items"][0]["quantity"] == Decimal("62")
        assert hasil["items"][0]["unit"] == "m3"

    @pytest.mark.asyncio
    async def test_daftar_bersih_dari_uang(self, repo, monkeypatch):
        async def _semua(
            po=None, proyek=None, pembuat=None, page=0, page_size=20, kata=None,
            urut=None, arah=None, keadaan=None,
        ):
            return {
                "total": 1,
                "data": [{
                    "id": 9, "name": "CoP-001",
                    "grossAmount": Decimal("52390000"),
                    "netAmount": Decimal("51390000"),
                    "items": [{"price": Decimal("845000")}],
                }],
            }

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "get_all", staticmethod(_semua)
        )
        hasil = await CoP.get_all(user_level=1)
        assert _sisir_uang(hasil) == []

    @pytest.mark.asyncio
    async def test_daftar_spk_bersih_dari_uang(self, repo, monkeypatch):
        async def _kandidat(project_name=None, keyword=None, batas=50):
            return [{"id": 5, "name": "013-SPK-MICZ-B", "projectName": "MICZ",
                     "purchaseType": "B", "customData": None, "date": None,
                     "dpp": 11035750000, "supplierName": "PT X"}]

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository,
            "spk_kandidat",
            staticmethod(_kandidat),
        )
        hasil = await CoP.spk_kandidat(user_level=1)
        assert _sisir_uang(hasil) == []
        # Nomor & proyeknya tetap terbaca — tanpa itu ia tak bisa memilih.
        assert hasil[0]["name"] == "013-SPK-MICZ-B"

    @pytest.mark.asyncio
    async def test_syarat_pajak_spk_tidak_bocor(self, repo, monkeypatch):
        """
        Tarif PPh, uang muka, dan retensi adalah susunan kesepakatan dengan
        pemasok. Tanpa nominal pun ia sudah menceritakan isinya.
        """
        repo["cop"] = {
            "id": 9, "name": "CoP-001", "purchaseOrderID": 5, "createdBy": 1,
            "isChecked": False, "isApproved": False,
            "grossAmount": Decimal("52390000"),
            "netAmount": Decimal("52390000"),
            "items": [], "adjustments": [],
        }
        hasil = await CoP.get_by_id(9, user_level=1)
        assert "spkSyarat" not in hasil
        assert _sisir_uang(hasil) == []

    @pytest.mark.asyncio
    async def test_pdf_ditolak(self, repo_cetak):
        """Lembar cetaknya memuat harga satuan dan nilai kontrak."""
        hasil = await CoP.data_cetak(9, user_level=1)
        assert hasil["status"] == 403

    @pytest.mark.asyncio
    async def test_tidak_boleh_mengisi_potongan(self, repo_penyesuaian):
        hasil = await CoP.set_penyesuaian(
            9, [_pot()], user_id=1, user_level=1, departments={"engineering"}
        )
        assert hasil["status"] == 403

    @pytest.mark.asyncio
    async def test_level_2_tetap_menerima_semuanya(self, repo, monkeypatch):
        """Penjagaannya tidak boleh kebablasan: pemeriksa TETAP melihat nilai."""
        repo["cop"] = {
            "id": 9, "name": "CoP-001", "purchaseOrderID": 5, "createdBy": 1,
            "isChecked": False, "isApproved": False,
            "grossAmount": Decimal("52390000"),
            "netAmount": Decimal("52390000"),
            "items": [{"purchaseOrderItemID": 11, "quantity": Decimal("62"),
                       "price": Decimal("845000"), "amount": Decimal("52390000")}],
            "adjustments": [],
        }
        hasil = await CoP.get_by_id(9, user_level=2)
        assert hasil["items"][0]["price"] == Decimal("845000")
        assert hasil["grossAmount"] == Decimal("52390000")


# =====================================================================
# 12. Periode WAJIB
# =====================================================================


class TestPeriodeWajib:
    """
    Berita acara progres tanpa rentang tanggal tidak dapat dibaca: ia
    menyatakan "sekian volume terlaksana" tanpa menyebut kapan, dan dua CoP
    berurutan menjadi mustahil dibedakan pekerjaannya.
    """

    @pytest.mark.asyncio
    async def test_tanpa_periode_ditolak(self, repo):
        muatan = _muatan(10)
        muatan.pop("periodStart")
        muatan.pop("periodEnd")
        hasil = await CoP.create(muatan, user_id=1, user_level=1,
                                 departments={"engineering"})
        assert hasil["status"] == 400
        assert repo["items_disimpan"] is None

    @pytest.mark.asyncio
    async def test_hanya_awal_ditolak(self, repo):
        muatan = _muatan(10)
        muatan.pop("periodEnd")
        hasil = await CoP.create(muatan, user_id=1, user_level=1,
                                 departments={"engineering"})
        assert hasil["status"] == 400

    @pytest.mark.asyncio
    async def test_akhir_mendahului_awal_ditolak(self, repo):
        """Skema menolak yang kosong; urutannya hanya dapat dijaga di sini."""
        import datetime as d

        muatan = _muatan(10)
        muatan["periodStart"] = d.date(2026, 8, 24)
        muatan["periodEnd"] = d.date(2026, 8, 18)
        hasil = await CoP.create(muatan, user_id=1, user_level=1,
                                 departments={"engineering"})
        assert hasil["status"] == 400
        assert "mendahului" in hasil["error"]

    @pytest.mark.asyncio
    async def test_awal_sama_dengan_akhir_boleh(self, repo):
        """Pekerjaan satu hari tetap sah."""
        import datetime as d

        muatan = _muatan(10)
        muatan["periodStart"] = d.date(2026, 8, 24)
        muatan["periodEnd"] = d.date(2026, 8, 24)
        hasil = await CoP.create(muatan, user_id=1, user_level=1,
                                 departments={"engineering"})
        assert "error" not in hasil

    @pytest.mark.asyncio
    async def test_menyunting_tidak_boleh_mengosongkan_periode(self, repo):
        repo["cop"] = {
            "id": 9, "createdBy": 1, "purchaseOrderID": 5, "isChecked": False,
            "periodStart": "2026-08-18", "periodEnd": "2026-08-24", "items": [],
        }
        hasil = await CoP.update(
            9, {"periodStart": None, "periodEnd": None},
            user_id=1, user_level=1, departments={"engineering"},
        )
        assert hasil["status"] == 400


# =====================================================================
# 13. Pagu uang muka & retensi
# =====================================================================


@pytest.fixture
def repo_pagu_dp(repo_penyesuaian, monkeypatch):
    """
    Kontrak 1.000.000.000 dengan uang muka 20% dan retensi 5%.

    Angka contohnya mengikuti keadaan yang ditanyakan pemilik: uang muka
    20%, progres pertama 10%, dipotong 20% sehingga tersisa 8%.
    """
    repo_penyesuaian["nilaiKontrak"] = Decimal("1000000000")
    repo_penyesuaian["spk"]["dpPercentage"] = 20.0
    repo_penyesuaian["spk"]["retentionPercentage"] = 5.0
    # Progres periode ini 10% dari kontrak.
    repo_penyesuaian["cop"]["grossAmount"] = Decimal("100000000")
    repo_penyesuaian["akumulasi"] = {}
    return repo_penyesuaian


class TestPaguUangMukaRetensi:
    """
    Uang muka dikembalikan sedikit demi sedikit dari tiap progres, dan
    akumulasinya tidak boleh melebihi uang muka yang benar-benar dibayarkan.
    """

    @pytest.mark.asyncio
    async def test_potongan_proporsional_diterima(self, repo_pagu_dp):
        """20% dari progres 100 juta = 20 juta; jauh di bawah pagu 200 juta."""
        hasil = await CoP.set_penyesuaian(
            9, [_pot("uang_muka", 20_000_000)], user_id=2, user_level=2,
            departments={"engineering"},
        )
        assert "error" not in hasil
        # 100 juta - 20 juta = 80 juta, alias 8% dari kontrak.
        assert hasil["netAmount"] == 80_000_000

    @pytest.mark.asyncio
    async def test_melebihi_sisa_uang_muka_ditolak(self, repo_pagu_dp):
        """Sudah dikembalikan 190 juta; 20 juta lagi berarti 210 dari 200."""
        repo_pagu_dp["akumulasi"] = {"deduction:uang_muka": Decimal("190000000")}
        hasil = await CoP.set_penyesuaian(
            9, [_pot("uang_muka", 20_000_000)], user_id=2, user_level=2,
            departments={"engineering"},
        )
        assert hasil["status"] == 400
        assert "uang muka" in hasil["error"]
        assert repo_pagu_dp["penyesuaian"] is None

    @pytest.mark.asyncio
    async def test_pas_menghabiskan_sisa_diterima(self, repo_pagu_dp):
        repo_pagu_dp["akumulasi"] = {"deduction:uang_muka": Decimal("190000000")}
        hasil = await CoP.set_penyesuaian(
            9, [_pot("uang_muka", 10_000_000)], user_id=2, user_level=2,
            departments={"engineering"},
        )
        assert "error" not in hasil

    @pytest.mark.asyncio
    async def test_pagu_retensi_dijaga_terpisah(self, repo_pagu_dp):
        """Retensi punya pagunya sendiri (5%), bukan berbagi dengan uang muka."""
        repo_pagu_dp["akumulasi"] = {"deduction:retensi": Decimal("49000000")}
        hasil = await CoP.set_penyesuaian(
            9, [_pot("retensi", 5_000_000)], user_id=2, user_level=2,
            departments={"engineering"},
        )
        assert hasil["status"] == 400
        assert "retensi" in hasil["error"]

    @pytest.mark.asyncio
    async def test_spk_tanpa_syarat_tidak_dijaga(self, repo_penyesuaian):
        """
        SPK lama yang tidak mencatat persentase apa pun tetap dapat dipotong.
        Pagu nol berarti "tidak tercatat", bukan "tidak boleh sama sekali".
        """
        repo_penyesuaian["nilaiKontrak"] = Decimal("1000000000")
        repo_penyesuaian["spk"]["dpPercentage"] = 0.0
        hasil = await CoP.set_penyesuaian(
            9, [_pot("uang_muka", 5_000_000)], user_id=2, user_level=2,
            departments={"engineering"},
        )
        assert "error" not in hasil

    @pytest.mark.asyncio
    async def test_pesan_menyebut_sisa_dan_seluruhnya(self, repo_pagu_dp):
        repo_pagu_dp["akumulasi"] = {"deduction:uang_muka": Decimal("190000000")}
        hasil = await CoP.set_penyesuaian(
            9, [_pot("uang_muka", 20_000_000)], user_id=2, user_level=2,
            departments={"engineering"},
        )
        pesan = hasil["error"]
        assert "10,000,000" in pesan or "10.000.000" in pesan
        assert "200,000,000" in pesan or "200.000.000" in pesan


class TestSaranPotongan:
    """
    Saran nominal untuk uang muka & retensi, dibatasi sisanya.

    Menyarankan angka yang pasti ditolak server hanya membuat yang mengisi
    mencoba-coba sendiri — karena itu saran pada periode terakhir dipotong
    sampai sisanya, bukan tetap 20% dari progres.
    """

    @pytest.mark.asyncio
    async def test_saran_proporsional(self, repo_pagu_dp, monkeypatch):
        async def _get(cop_id):
            return dict(repo_pagu_dp["cop"])

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "get_by_id", staticmethod(_get)
        )
        hasil = await CoP.get_by_id(9, user_level=2)
        sy = hasil["spkSyarat"]
        assert sy["saranUangMuka"] == 20_000_000   # 20% x 100 juta
        assert sy["saranRetensi"] == 5_000_000     # 5%  x 100 juta
        assert sy["dpPagu"] == 200_000_000
        assert sy["dpSisa"] == 200_000_000

    @pytest.mark.asyncio
    async def test_saran_dibatasi_sisa(self, repo_pagu_dp, monkeypatch):
        """Periode terakhir: sisa uang muka tinggal 5 juta, saran ikut 5 juta."""
        repo_pagu_dp["akumulasi"] = {"deduction:uang_muka": Decimal("195000000")}

        async def _get(cop_id):
            return dict(repo_pagu_dp["cop"])

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "get_by_id", staticmethod(_get)
        )
        hasil = await CoP.get_by_id(9, user_level=2)
        sy = hasil["spkSyarat"]
        assert sy["dpSisa"] == 5_000_000
        assert sy["saranUangMuka"] == 5_000_000

    @pytest.mark.asyncio
    async def test_pengembalian_menutup_sendiri_saat_selesai(self, repo_pagu_dp, monkeypatch):
        """
        Sifat yang membuat cara ini benar: bila TIAP progres dipotong 20%,
        maka ketika progres mencapai 100% jumlah yang dikembalikan tepat
        sebesar uang mukanya. Tidak ada yang perlu diakali di periode akhir.
        """
        kontrak = Decimal("1000000000")
        tarif = Decimal("20")
        # Lima periode, masing-masing 20% dari kontrak.
        progres = [kontrak * Decimal("0.2")] * 5
        total_kembali = sum((p * tarif / 100 for p in progres), Decimal("0"))
        assert total_kembali == kontrak * tarif / 100  # = uang mukanya


class TestPencarianDaftar:
    """
    Kata pencarian diteruskan ke penyimpanan, bukan dipakai menyaring hasil.

    Daftar ini dipenggal per halaman. Menyaring satu halaman di layar hanya
    mencari di baris yang kebetulan terbuka — yang dicari kerap ada di
    halaman ketiga, dan layar menjawab "tidak ada" untuk dokumen yang ada.
    """

    @pytest.mark.asyncio
    async def test_kata_diteruskan_ke_penyimpanan(self, monkeypatch):
        diterima = {}

        async def _semua(po=None, proyek=None, pembuat=None, page=0, page_size=20,
                         kata=None, urut=None, arah=None, keadaan=None):
            diterima["kata"] = kata
            return {"total": 0, "data": []}

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "get_all", staticmethod(_semua)
        )
        await CoP.get_all(user_level=2, keyword="R501")
        assert diterima["kata"] == "R501"

    @pytest.mark.asyncio
    async def test_tanpa_kata_tetap_none(self, monkeypatch):
        diterima = {}

        async def _semua(po=None, proyek=None, pembuat=None, page=0, page_size=20,
                         kata=None, urut=None, arah=None, keadaan=None):
            diterima["kata"] = kata
            return {"total": 0, "data": []}

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "get_all", staticmethod(_semua)
        )
        await CoP.get_all(user_level=2)
        assert diterima["kata"] is None

    @pytest.mark.asyncio
    async def test_hasil_pencarian_tetap_disaring_untuk_level_1(self, monkeypatch):
        """
        Pencarian TIDAK membuka jalan pintas ke nilai rupiah.

        Ini bukan pengulangan tanpa guna: jalur pencarian adalah jalur baru
        menuju daftar yang sama, dan penyaring nilai yang dipasang di satu
        jalur mudah tertinggal di jalur berikutnya.
        """

        async def _semua(po=None, proyek=None, pembuat=None, page=0, page_size=20,
                         kata=None, urut=None, arah=None, keadaan=None):
            return {
                "total": 1,
                "data": [{
                    "id": 9, "name": "CoP-001",
                    "grossAmount": Decimal("52390000"),
                    "netAmount": Decimal("51390000"),
                    "items": [{"price": Decimal("845000")}],
                }],
            }

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "get_all", staticmethod(_semua)
        )
        hasil = await CoP.get_all(user_level=1, keyword="CoP")
        bocor = _sisir_uang(hasil)
        assert not bocor, f"nilai rupiah bocor lewat pencarian: {bocor}"


class TestPemasokPadaKandidatSpk:
    """
    Alamat pemasok ikut ke layar — termasuk ke level 1.

    Ia BUKAN nilai rupiah. Yang mengisi volume tetap perlu memastikan SPK
    yang dipegangnya milik pemasok yang benar, dan nomor SPK yang mirip
    justru dibedakan oleh ini. Menahannya "karena level 1" adalah salah
    paham tentang apa yang sebenarnya dijaga.
    """

    @staticmethod
    def _spk():
        return {
            "id": 5,
            "name": "013-SPK-MICZ-B",
            "projectName": "MICZ",
            "purchaseType": "B",
            "customData": None,
            "date": None,
            "dpp": Decimal("500000000"),
            "supplierName": "PT. Subadi Karya",
            "supplierAddress": "Jalan Cisaranten Kulon No. 66-H, Bandung",
        }

    @pytest.mark.asyncio
    async def test_alamat_sampai_ke_level_1(self, monkeypatch):
        async def _kandidat(proyek=None, kata=None):
            return [TestPemasokPadaKandidatSpk._spk()]

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository,
            "spk_kandidat",
            staticmethod(_kandidat),
        )
        hasil = await CoP.spk_kandidat(user_level=1)
        assert len(hasil) == 1
        assert hasil[0]["supplierName"] == "PT. Subadi Karya"
        assert hasil[0]["supplierAddress"].startswith("Jalan Cisaranten")

    @pytest.mark.asyncio
    async def test_alamat_tidak_menyeret_nilai_kontrak(self, monkeypatch):
        """
        Yang DIJAGA tetap dijaga.

        Baris yang sama membawa `dpp`; kalau penyaringnya kendur saat alamat
        ditambahkan, nilai kontrak ikut lolos lewat pintu yang sama.
        """

        async def _kandidat(proyek=None, kata=None):
            return [TestPemasokPadaKandidatSpk._spk()]

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository,
            "spk_kandidat",
            staticmethod(_kandidat),
        )
        hasil = await CoP.spk_kandidat(user_level=1)
        bocor = _sisir_uang(hasil)
        assert not bocor, f"nilai rupiah bocor lewat kandidat SPK: {bocor}"
        assert "dpp" not in hasil[0]

    @pytest.mark.asyncio
    async def test_level_2_tetap_menerima_dpp(self, monkeypatch):
        async def _kandidat(proyek=None, kata=None):
            return [TestPemasokPadaKandidatSpk._spk()]

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository,
            "spk_kandidat",
            staticmethod(_kandidat),
        )
        hasil = await CoP.spk_kandidat(user_level=2)
        assert hasil[0]["dpp"] == 500_000_000
        assert hasil[0]["supplierAddress"]


class TestUrutanDaftar:
    """
    Nama kolom pengurutan masuk ke SQL sebagai TEKS.

    Ia tidak dapat dijadikan parameter — `ORDER BY :kolom` tidak berlaku di
    MySQL — sehingga apa pun yang lolos dari daftar putih berjalan sebagai
    SQL. Karena itu yang diuji di sini bukan kenyamanannya, melainkan bahwa
    yang tidak dikenali tidak pernah sampai ke pernyataan.
    """

    def test_tanpa_permintaan_pakai_bawaan(self):
        assert Repo._urutan(None, None) == "c.date DESC, c.id DESC"

    def test_kolom_dikenali(self):
        assert Repo._urutan("tanggal", "asc") == "c.date ASC, c.id DESC"
        assert Repo._urutan("nilai", "desc") == "c.netAmount DESC, c.id DESC"
        assert Repo._urutan("pemasok", "asc") == "s.name ASC, c.id DESC"

    def test_kolom_asing_diabaikan_bukan_diteruskan(self):
        """Yang tidak dikenali jatuh ke bawaan — tidak pernah masuk SQL."""
        for jahat in (
            "c.id; DROP TABLE certificate_of_payments",
            "(SELECT password FROM users LIMIT 1)",
            "name UNION SELECT 1",
            "",
            "   ",
        ):
            assert Repo._urutan(jahat, "asc") == "c.date DESC, c.id DESC"

    def test_arah_hanya_dua_kemungkinan(self):
        """Arah pun tidak diteruskan apa adanya."""
        assert Repo._urutan("tanggal", "asc").endswith("c.id DESC")
        assert " ASC," in Repo._urutan("tanggal", "asc")
        # Apa pun selain 'asc' menjadi DESC — termasuk yang mencoba menyisip.
        for jahat in ("desc", "DESC", "; DROP TABLE x", None, "asc; --"):
            hasil = Repo._urutan("tanggal", jahat)
            assert hasil in (
                "c.date ASC, c.id DESC",
                "c.date DESC, c.id DESC",
            ), hasil
            assert ";" not in hasil

    def test_keadaan_urut_mengikuti_perjalanan_dokumen(self):
        """
        Draf -> diperiksa -> disetujui, bukan menurut abjad.

        Itulah urutan yang berarti bagi yang membacanya; menurut abjad,
        "diperiksa" mendahului "draf" dan daftarnya tidak menyatakan apa-apa.
        """
        hasil = Repo._urutan("keadaan", "asc")
        assert hasil == "c.isApproved ASC, c.isChecked ASC, c.id DESC"

    @pytest.mark.asyncio
    async def test_urutan_diteruskan_ke_penyimpanan(self, monkeypatch):
        diterima = {}

        async def _semua(po=None, proyek=None, pembuat=None, page=0, page_size=20,
                         kata=None, urut=None, arah=None, keadaan=None):
            diterima["urut"] = urut
            diterima["arah"] = arah
            return {"total": 0, "data": []}

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "get_all", staticmethod(_semua)
        )
        await CoP.get_all(user_level=2, sort_by="nilai", sort_dir="asc")
        assert diterima == {"urut": "nilai", "arah": "asc"}


class TestPenomoranDokumen:
    """
    Nomor CoP: 001-R501-VIII-2026.

    Angka pertama urutan DOKUMEN dalam proyek — berjalan terus, tidak pernah
    kembali ke 1. Bulan romawi dan tahun menerangkan kapan berkasnya terbit.
    """

    def test_bentuk_nomor(self):
        import datetime as d

        assert (
            Repo.susun_nama(1, "R501", d.date(2026, 8, 25)) == "001-R501-VIII-2026"
        )
        assert (
            Repo.susun_nama(37, "MICZ", d.date(2026, 1, 3)) == "037-MICZ-I-2026"
        )
        assert (
            Repo.susun_nama(128, "R501", d.date(2025, 12, 31))
            == "128-R501-XII-2025"
        )

    def test_bulan_diambil_dari_tanggal_dokumen(self):
        """
        BUKAN dari hari ini.

        CoP bertanggal 31 Agustus yang baru sempat dimasukkan 2 September
        harus tetap bernomor VIII: nomornya menerangkan dokumennya, bukan
        kapan orang mengetiknya.
        """
        import datetime as d

        assert "-VIII-" in Repo.susun_nama(9, "R501", d.date(2026, 8, 31))
        assert "-IX-" in Repo.susun_nama(9, "R501", d.date(2026, 9, 1))

    def test_seluruh_dua_belas_bulan(self):
        import datetime as d

        harap = [
            "I", "II", "III", "IV", "V", "VI",
            "VII", "VIII", "IX", "X", "XI", "XII",
        ]
        for bulan, romawi in enumerate(harap, start=1):
            nama = Repo.susun_nama(1, "P", d.date(2026, bulan, 15))
            assert nama == f"001-P-{romawi}-2026", nama

    def test_nomor_diisi_nol_di_depan(self):
        import datetime as d

        assert Repo.susun_nama(7, "P", d.date(2026, 5, 1)).startswith("007-")
        # Melewati tiga digit tidak dipotong: dokumen ke-1234 tetap utuh.
        assert Repo.susun_nama(1234, "P", d.date(2026, 5, 1)).startswith("1234-")

    def test_proyek_kosong_tidak_menghasilkan_nomor_pincang(self):
        """
        Proyek kosong menjadi tanda pisah, bukan untai kosong.

        "001--VIII-2026" punya dua tanda hubung berturut-turut dan terbaca
        seperti nomor yang rusak; "001---VIII-2026" pun tidak lebih baik.
        Yang penting: bentuknya tetap empat bagian.
        """
        import datetime as d

        nama = Repo.susun_nama(1, "", d.date(2026, 8, 1))
        assert nama == "001---VIII-2026" or nama.count("-") >= 3
        assert "VIII" in nama

    @pytest.mark.asyncio
    async def test_nomor_dokumen_memakai_max_bukan_count(self, monkeypatch):
        """
        Dokumen TERHAPUS tetap memakan nomornya.

        Dengan COUNT, menghapus dokumen ke-3 membuat dokumen berikutnya
        kembali bernomor 003 — padahal salinan yang lama mungkin sudah
        beredar, dan dua berkas berbeda bernomor sama tidak dapat
        diselesaikan belakangan.
        """
        sql_terpakai = {}

        async def _fetch_val(query, values=None):
            sql_terpakai["q"] = " ".join(str(query).split())
            return 12

        monkeypatch.setattr(
            "repository.certificate_of_payment_repository.database.fetch_val",
            _fetch_val,
        )
        hasil = await Repo.nomor_dokumen_berikut("R501")
        assert hasil == 13
        assert "MAX(documentNumber)" in sql_terpakai["q"]
        assert "COUNT" not in sql_terpakai["q"].upper()

    @pytest.mark.asyncio
    async def test_proyek_pertama_mulai_dari_satu(self, monkeypatch):
        async def _fetch_val(query, values=None):
            return None

        monkeypatch.setattr(
            "repository.certificate_of_payment_repository.database.fetch_val",
            _fetch_val,
        )
        assert await Repo.nomor_dokumen_berikut("BARU") == 1


class TestCetakSetelahDiperiksa:
    """
    CoP tidak dapat dicetak sebelum diperiksa; BAP tetap bisa.

    Lembar CoP menyatakan nilai tagihan, dan sebelum diperiksa angkanya belum
    ditelaah siapa pun — potongan uang muka dan retensi bahkan belum tentu
    dimasukkan. Begitu keluar dari pencetak, lembar itu tidak dapat dibedakan
    dari yang sudah benar.

    BAP menyatakan volume yang terlaksana, bukan nilai yang dibayar — dan
    justru itulah lembar yang dibawa ke lapangan untuk diperiksa lebih dulu.
    """

    @staticmethod
    def _pasang(monkeypatch, is_checked):
        async def _get(cop_id):
            return {
                "id": 9, "name": "001-R501-VIII-2026", "number": 1,
                "purchaseOrderID": 5, "projectName": "R501",
                "date": None, "periodStart": None, "periodEnd": None,
                "isChecked": is_checked, "isApproved": 0,
                "items": [], "adjustments": [],
                "grossAmount": Decimal("0"), "deductionTotal": Decimal("0"),
                "additionTotal": Decimal("0"), "netAmount": Decimal("0"),
            }

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "get_by_id", staticmethod(_get)
        )

    @pytest.mark.asyncio
    async def test_cop_ditolak_sebelum_diperiksa(self, monkeypatch):
        self._pasang(monkeypatch, is_checked=0)
        hasil = await CoP.data_cetak(9, user_level=3, sertakan_cop=True)
        assert "error" in hasil
        assert hasil["status"] == 409
        # Pesannya menyebut jalan keluarnya, bukan sekadar menolak.
        assert "Berita Acara" in hasil["error"]

    @pytest.mark.asyncio
    async def test_bap_tetap_boleh_sebelum_diperiksa(self, monkeypatch):
        """
        Yang dijaga adalah CoP, bukan seluruh pencetakan.

        Kalau penjagaannya dipasang pada `data_cetak` tanpa membedakan
        keduanya, BAP ikut terkunci — dan yang di lapangan tidak punya lembar
        untuk diperiksa, sehingga tidak ada yang dapat diperiksa sama sekali.
        """
        self._pasang(monkeypatch, is_checked=0)
        hasil = await CoP.data_cetak(9, user_level=3, sertakan_cop=False)
        # Lolos penjagaan; berhenti belakangan karena SPK tiruan tidak ada.
        assert hasil.get("status") != 409

    @pytest.mark.asyncio
    async def test_sudah_diperiksa_lolos_penjagaan(self, monkeypatch):
        self._pasang(monkeypatch, is_checked=1)
        hasil = await CoP.data_cetak(9, user_level=3, sertakan_cop=True)
        assert hasil.get("status") != 409

    @pytest.mark.asyncio
    async def test_level_1_tetap_ditolak_lebih_dulu(self, monkeypatch):
        """
        Penjagaan LAMA tidak tergeser oleh yang baru.

        Level 1 ditolak karena lembarnya memuat harga — alasan yang berdiri
        sendiri, dan harus tetap berlaku pada dokumen yang sudah diperiksa.
        """
        self._pasang(monkeypatch, is_checked=1)
        hasil = await CoP.data_cetak(9, user_level=1, sertakan_cop=True)
        assert hasil["status"] == 403


class TestPenagihanCoP:
    """
    Satu CoP hanya boleh menjadi dasar SATU pembelian yang aktif.

    Keadaan "sudah ditagihkan" TIDAK disimpan sebagai penanda pada CoP,
    melainkan disimpulkan dari ada tidaknya pembelian aktif yang menunjuknya.
    Akibatnya menghapus pembelian membuka kembali CoP-nya dengan sendirinya —
    tidak ada penanda kedua yang dapat tertinggal tidak sejalan.
    """

    @staticmethod
    def _cop(disetujui=1):
        return {
            "id": 9, "name": "001-R501-VIII-2026", "number": 1,
            "purchaseOrderID": 5, "projectName": "R501",
            "isChecked": 1, "isApproved": disetujui,
            "items": [], "adjustments": [],
            "netAmount": Decimal("52390000"),
        }

    @pytest.mark.asyncio
    async def test_belum_disetujui_tidak_boleh_ditagih(self, monkeypatch):
        async def _get(cop_id):
            return dict(TestPenagihanCoP._cop(disetujui=0))

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "get_by_id", staticmethod(_get)
        )
        galat = await CoP.periksa_boleh_ditagih(9)
        assert galat is not None
        assert galat["status"] == 409
        assert "belum disetujui" in galat["error"].lower()

    @pytest.mark.asyncio
    async def test_sudah_ditagihkan_ditolak(self, monkeypatch):
        async def _get(cop_id):
            return dict(TestPenagihanCoP._cop())

        async def _tagihan(cop_id):
            return {"id": 77, "invoiceName": "INV-0042"}

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "get_by_id", staticmethod(_get)
        )
        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "tagihan", staticmethod(_tagihan)
        )
        galat = await CoP.periksa_boleh_ditagih(9)
        assert galat["status"] == 409
        # Pesannya MENYEBUT pembelian yang sudah ada — tanpa itu yang
        # membacanya tidak tahu ke mana harus mencari.
        assert "INV-0042" in galat["error"]

    @pytest.mark.asyncio
    async def test_disetujui_dan_belum_ditagih_lolos(self, monkeypatch):
        async def _get(cop_id):
            return dict(TestPenagihanCoP._cop())

        async def _tagihan(cop_id):
            return None

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "get_by_id", staticmethod(_get)
        )
        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "tagihan", staticmethod(_tagihan)
        )
        assert await CoP.periksa_boleh_ditagih(9) is None

    @pytest.mark.asyncio
    async def test_pembelian_terhapus_membuka_kembali(self, monkeypatch):
        """
        Yang menjaga bukan penanda, melainkan barisnya sendiri.

        `tagihan()` hanya melihat pembelian dengan `isDelete = 0`. Karena itu
        menghapus pembelian yang salah membuat CoP-nya dapat ditagihkan lagi
        tanpa satu pun langkah pemulihan — dan tidak ada penanda yang dapat
        tertinggal menyala.
        """
        keadaan = {"terhapus": False}

        async def _get(cop_id):
            return dict(TestPenagihanCoP._cop())

        async def _tagihan(cop_id):
            return None if keadaan["terhapus"] else {"id": 77, "invoiceName": "X"}

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "get_by_id", staticmethod(_get)
        )
        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "tagihan", staticmethod(_tagihan)
        )

        assert (await CoP.periksa_boleh_ditagih(9))["status"] == 409
        keadaan["terhapus"] = True
        assert await CoP.periksa_boleh_ditagih(9) is None

    @pytest.mark.asyncio
    async def test_siap_tagih_ditolak_level_1(self, monkeypatch):
        """Daftar ini menyebut nilai bersih tiap dokumen."""
        hasil = await CoP.siap_tagih(user_level=1)
        assert hasil["status"] == 403

    @pytest.mark.asyncio
    async def test_siap_tagih_meneruskan_tarif_pajak(self, monkeypatch):
        """
        Tarif PPN & PPh ikut, supaya formulir pembelian tidak perlu
        menanyakan SPK-nya sekali lagi — dan supaya PPh yang dipotong memang
        tarif SPK-nya, bukan angka yang diketik ulang.
        """

        async def _siap(kata=None, batas=30):
            return [{
                "id": 9, "name": "001-R501-VIII-2026", "number": 1,
                "projectName": "R501", "date": None,
                "periodStart": None, "periodEnd": None,
                "netAmount": Decimal("52390000"),
                "purchaseOrderID": 5, "purchaseOrderName": "008-SPK-R501-B",
                "purchaseType": "B", "customData": None,
                "supplierID": 3, "supplierName": "PT. X",
                "supplierAddress": "Jl. Y",
                "ppn": Decimal("11"), "pphCode": "23-100-09",
                "pphTaxObject": "Jasa", "pphPercentage": 2.0,
            }]

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "siap_tagih", staticmethod(_siap)
        )
        hasil = await CoP.siap_tagih(user_level=2)
        assert len(hasil) == 1
        assert hasil[0]["ppn"] == 11
        assert hasil[0]["pphPercentage"] == 2
        assert hasil[0]["pphCode"] == "23-100-09"
        assert hasil[0]["netAmount"] == 52_390_000


class TestPphBukanPotonganCoP:
    """
    PPh dipotong pada PEMBELIAN, bukan pada certificate of payment.

    Tabel `purchases` punya `pphPercentage` sendiri dan nilai tagihannya
    memang dihitung dengan mengurangkan PPh dari DPP. Mencatatnya juga
    sebagai potongan CoP berarti satu potongan yang sama tersimpan pada dua
    dokumen — dan tidak ada cara mengetahui apakah ia dipotong sekali atau
    dua kali.
    """

    def test_pph_bukan_kategori_potongan(self):
        from models.certificate_of_payment_model import KATEGORI_POTONGAN

        assert "pph" not in KATEGORI_POTONGAN
        # Yang lain tetap ada — PPh dilepas, bukan daftarnya dikosongkan.
        assert "uang_muka" in KATEGORI_POTONGAN
        assert "retensi" in KATEGORI_POTONGAN
        assert "denda" in KATEGORI_POTONGAN

    @pytest.mark.asyncio
    async def test_pph_ditolak_sebagai_potongan(self, repo, monkeypatch):
        """
        Muatan yang tetap mengirimkannya DITOLAK, bukan diterima diam-diam.

        Layar lama masih dapat mengirimkannya sampai semua orang menyegarkan
        perambannya; yang diterima diam-diam akan memotong dua kali.
        """
        hasil = await CoP.set_penyesuaian(
            9,
            [{"kind": "deduction", "category": "pph", "amount": 100000}],
            user_id=2,
            user_level=3,
        )
        assert "error" in hasil


class TestSaringKeadaan:
    """
    Keadaan dokumen disaring di SERVER, bukan di layar.

    Ia disimpulkan dari `isChecked`/`isApproved`, bukan disimpan sebagai satu
    kolom — dan menyaringnya di layar keliru pada daftar berhalaman: yang
    tersaring hanya baris yang kebetulan terbuka, sementara `total` tetap
    menghitung semuanya.
    """

    @pytest.mark.asyncio
    async def test_keadaan_diteruskan_ke_penyimpanan(self, monkeypatch):
        diterima = {}

        async def _semua(po=None, proyek=None, pembuat=None, page=0, page_size=20,
                         kata=None, urut=None, arah=None, keadaan=None):
            diterima["keadaan"] = keadaan
            return {"total": 0, "data": []}

        monkeypatch.setattr(
            modul.CertificateOfPaymentRepository, "get_all", staticmethod(_semua)
        )
        await CoP.get_all(user_level=2, keadaan="diperiksa")
        assert diterima["keadaan"] == "diperiksa"

    def test_tiga_keadaan_menutup_seluruh_kemungkinan(self):
        """
        Draft / diperiksa / disetujui harus SALING LEPAS dan MENUTUP semua.

        Bila ada dokumen yang tidak masuk salah satunya, ia hilang dari
        ketiga keping penyaring sekaligus — dan tidak ada apa pun di layar
        yang memberitahu bahwa ia ada.
        """
        for checked in (0, 1):
            for approved in (0, 1):
                # `isApproved` selalu menyiratkan sudah diperiksa; keadaan
                # (0,1) tidak terbentuk oleh alur mana pun.
                if approved and not checked:
                    continue
                cocok = [
                    nama
                    for nama, uji in (
                        ("draft", not checked),
                        ("diperiksa", checked and not approved),
                        ("disetujui", approved),
                    )
                    if uji
                ]
                assert len(cocok) == 1, (checked, approved, cocok)
