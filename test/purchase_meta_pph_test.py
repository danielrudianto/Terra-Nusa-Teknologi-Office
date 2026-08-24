"""
Pengujian sunting META pembelian luar — khususnya kode & objek PPh.

Aturan yang dijaga:

  * Kode & objek PPh (pphCode, pphTaxObject) adalah KLASIFIKASI, bukan
    nominal. Boleh dibetulkan meski pembayarannya sudah ada — kasus nyatanya
    kode PPh lupa diisi padahal tarifnya 0%.

  * Nilai yang benar-benar mengubah nominal (dpp, ppn, pphPercentage) tetap
    DIKUNCI begitu ada pembayaran melekat.

  * Hanya level 5.

Diuji karena jalur ini menyentuh dokumen yang menjadi dasar pembayaran ke
pihak ketiga, dan pemisahan "klasifikasi" vs "nominal" mudah bergeser tanpa
disadari — menghapusnya tidak membuat apa pun gagal, hanya penjagaannya
kehilangan guna.
"""

from types import SimpleNamespace

import pytest

PurchaseController = None


@pytest.fixture
def repo(monkeypatch):
    """
    Tiru repository & penghitung pembayaran. Yang diuji keputusan controller,
    bukan penyimpanannya — jadi tidak ada MySQL yang perlu dijalankan.
    """
    keadaan = {
        "lama": {
            "id": 1,
            "dpp": 1000000,
            "ppn": 11,
            "pphPercentage": 0,
            "pphCode": None,
            "pphTaxObject": None,
            "date": "2026-08-01",
            "invoiceName": "INV-1",
            "receiptName": "KW-1",
            "taxInvoiceName": None,
        },
        "pembayaran_aktif": 0,   # diubah per-test
        "update_dipanggil": False,
        "update_data": None,
    }

    global PurchaseController
    from controllers import purchase_controller as modul

    PurchaseController = modul.PurchaseController

    async def _get_by_id(pid):
        return dict(keadaan["lama"])

    async def _hitung(pid):
        return keadaan["pembayaran_aktif"]

    async def _update(pid, data, user_id):
        keadaan["update_dipanggil"] = True
        keadaan["update_data"] = dict(data)
        return {"message": "Purchase updated successfully"}

    monkeypatch.setattr(
        modul.PurchaseRepository, "get_by_id", staticmethod(_get_by_id)
    )
    monkeypatch.setattr(
        modul.PurchaseRepository, "update", staticmethod(_update)
    )
    monkeypatch.setattr(
        modul.PaymentOutgoingRepository,
        "hitung_pembayaran_aktif",
        staticmethod(_hitung),
    )
    return keadaan


@pytest.mark.asyncio
async def test_level_di_bawah_5_ditolak(repo):
    hasil = await PurchaseController.update_purchase_meta(
        1, {"pphCode": "24-104-56"}, userID=9, userLevel=4
    )
    assert hasil["status"] == 403
    assert hasil["error"] == "FORBIDDEN_LEVEL"
    assert repo["update_dipanggil"] is False


@pytest.mark.asyncio
async def test_kode_pph_boleh_diubah_meski_ada_pembayaran(repo):
    """Inti fitur: kode & objek PPh = klasifikasi, tidak terkunci pembayaran."""
    repo["pembayaran_aktif"] = 3  # ada pembayaran melekat

    hasil = await PurchaseController.update_purchase_meta(
        1,
        {"pphCode": "24-104-56", "pphTaxObject": "Jasa pengangkutan"},
        userID=1,
        userLevel=5,
    )

    assert "error" not in hasil
    assert repo["update_dipanggil"] is True
    assert repo["update_data"]["pphCode"] == "24-104-56"
    assert repo["update_data"]["pphTaxObject"] == "Jasa pengangkutan"


@pytest.mark.asyncio
async def test_tarif_pph_terkunci_saat_ada_pembayaran(repo):
    """pphPercentage mengubah NOMINAL potongan -> terkunci setelah pembayaran."""
    repo["pembayaran_aktif"] = 1

    hasil = await PurchaseController.update_purchase_meta(
        1, {"pphPercentage": 2}, userID=1, userLevel=5
    )

    assert hasil["status"] == 409
    assert hasil["error"] == "PURCHASE_HAS_PAYMENTS"
    assert repo["update_dipanggil"] is False


@pytest.mark.asyncio
async def test_dpp_terkunci_saat_ada_pembayaran(repo):
    repo["pembayaran_aktif"] = 1
    hasil = await PurchaseController.update_purchase_meta(
        1, {"dpp": 2000000}, userID=1, userLevel=5
    )
    assert hasil["status"] == 409
    assert repo["update_dipanggil"] is False


@pytest.mark.asyncio
async def test_nilai_boleh_diubah_saat_belum_ada_pembayaran(repo):
    repo["pembayaran_aktif"] = 0
    hasil = await PurchaseController.update_purchase_meta(
        1, {"dpp": 2000000, "pphPercentage": 2}, userID=1, userLevel=5
    )
    assert "error" not in hasil
    assert repo["update_dipanggil"] is True
    assert repo["update_data"]["dpp"] == 2000000


@pytest.mark.asyncio
async def test_kode_pph_plus_tarif_saat_ada_pembayaran_tetap_ditolak(repo):
    """
    Bila layar (versi lama) ikut mengirim tarif yang BERUBAH bersama kodenya
    saat sudah ada pembayaran, penolakan harus tetap terjadi — nominalnya
    tidak boleh bergeser. Kode saja yang bebas.
    """
    repo["pembayaran_aktif"] = 1
    hasil = await PurchaseController.update_purchase_meta(
        1,
        {"pphCode": "24-104-56", "pphPercentage": 2},
        userID=1,
        userLevel=5,
    )
    assert hasil["status"] == 409
    assert repo["update_dipanggil"] is False


@pytest.mark.asyncio
async def test_field_asing_dibuang(repo):
    """Muatan asing (mis. isDelete) tidak boleh pernah sampai ke repository."""
    repo["pembayaran_aktif"] = 0
    hasil = await PurchaseController.update_purchase_meta(
        1,
        {"pphCode": "24-104-56", "isDelete": True, "id": 999},
        userID=1,
        userLevel=5,
    )
    assert "error" not in hasil
    assert "isDelete" not in repo["update_data"]
    assert "id" not in repo["update_data"]
    assert repo["update_data"]["pphCode"] == "24-104-56"
