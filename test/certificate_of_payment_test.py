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
