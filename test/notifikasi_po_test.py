"""
Pengujian kabar push pada alur purchase order.

Rantainya:

  1. PO dibuat        -> pemeriksa: "Minta diperiksa"   (sudah diuji terpisah)
  2. Selesai diperiksa -> penyetuju: "Minta disetujui"
                          pembuat  : "Selesai diperiksa"
  3. approved/cancelled -> pembuat : "Disetujui" / "Ditolak"

Yang dijaga di sini nomor 2 dan 3, beserta pengecualiannya:

  * pencabutan pemeriksaan TIDAK berkabar — bukan kemajuan, dan pembuat
    justru panik menerima "dicabut" tanpa konteks;
  * pengambil keputusan tidak diberi tahu atas tekanannya sendiri;
  * kegagalan repository tidak menghasilkan kabar apa pun;
  * kembali ke draf bukan hasil — tidak membangunkan ponsel siapa pun.

Push adalah EFEK SAMPING: pengujian juga memastikan hasil fungsi utamanya
tidak berubah oleh ada/tidaknya notifikasi.
"""

import pytest

from controllers import purchase_order_controller as modul
from controllers.purchase_order_controller import PurchaseOrderController

import utils.webpush as webpush
from repository.push_subscription_repository import PushSubscriptionRepository


@pytest.fixture
def kabar(monkeypatch):
    """Tangkap semua kiriman push; tidak ada jaringan yang disentuh."""
    catatan = []

    def _kirim(user_ids, judul, pesan, url="/", tag=None, data_tambahan=None):
        catatan.append(
            {
                "ke": list(user_ids),
                "judul": judul,
                "pesan": pesan,
                "url": url,
                "tag": tag,
            }
        )

        async def _noop():
            return None

        return _noop()

    monkeypatch.setattr(webpush, "kirim_ke_pengguna", _kirim)
    monkeypatch.setattr(webpush, "push_aktif", lambda: True)
    return catatan


@pytest.fixture
def po(monkeypatch):
    """PO contoh: dibuat oleh user 10."""
    data = {
        "id": 55,
        "name": "TNT-PO-055",
        "projectName": "Gudang A",
        "createdBy": 10,
    }

    async def _get_by_id(pid):
        return dict(data)

    monkeypatch.setattr(
        modul.PurchaseOrderRepository, "get_by_id", staticmethod(_get_by_id)
    )
    return data


@pytest.fixture
def penyetuju(monkeypatch):
    async def _ids(kecuali_user_ids=None):
        kecuali = set(kecuali_user_ids or [])
        return [u for u in (4, 5) if u not in kecuali]

    monkeypatch.setattr(
        PushSubscriptionRepository, "penyetuju_ids", staticmethod(_ids)
    )


def _set_checked_sukses(monkeypatch):
    async def _ok(pid, checked, user_id, user_level=None, departments=None):
        return {"message": "ok"}

    monkeypatch.setattr(
        modul.PurchaseOrderRepository, "set_checked", staticmethod(_ok)
    )


@pytest.mark.asyncio
async def test_selesai_periksa_kabari_penyetuju_dan_pembuat(
    monkeypatch, kabar, po, penyetuju
):
    _set_checked_sukses(monkeypatch)

    hasil = await PurchaseOrderController.set_checked(
        55, True, user_id=3, user_level=3
    )

    assert hasil == {"message": "ok"}
    judul = sorted(k["judul"] for k in kabar)
    assert judul == ["Minta disetujui", "Selesai diperiksa"]

    minta = next(k for k in kabar if k["judul"] == "Minta disetujui")
    assert minta["ke"] == [4, 5]
    assert "TNT-PO-055" in minta["pesan"]
    assert "Gudang A" in minta["pesan"]

    selesai = next(k for k in kabar if k["judul"] == "Selesai diperiksa")
    assert selesai["ke"] == [10]


@pytest.mark.asyncio
async def test_pencabutan_tidak_berkabar(monkeypatch, kabar, po, penyetuju):
    _set_checked_sukses(monkeypatch)
    await PurchaseOrderController.set_checked(55, False, user_id=3, user_level=4)
    assert kabar == []


@pytest.mark.asyncio
async def test_periksa_gagal_tidak_berkabar(monkeypatch, kabar, po, penyetuju):
    async def _gagal(pid, checked, user_id, user_level=None, departments=None):
        return {"error": "FORBIDDEN", "status": 403}

    monkeypatch.setattr(
        modul.PurchaseOrderRepository, "set_checked", staticmethod(_gagal)
    )
    await PurchaseOrderController.set_checked(55, True, user_id=3, user_level=1)
    assert kabar == []


@pytest.mark.asyncio
async def test_pemeriksa_adalah_pembuat_level5_tanpa_kabar_ganda(
    monkeypatch, kabar, po, penyetuju
):
    """Pembuat (10) memeriksa sendiri (level 5 boleh): ia tidak dikabari."""
    _set_checked_sukses(monkeypatch)
    await PurchaseOrderController.set_checked(55, True, user_id=10, user_level=5)
    assert [k["judul"] for k in kabar] == ["Minta disetujui"]
    assert kabar[0]["ke"] == [4, 5]


def _update_status_sukses(monkeypatch):
    async def _ok(pid, status, user_id, user_level=None):
        return {"message": "ok"}

    monkeypatch.setattr(
        modul.PurchaseOrderRepository, "update_status", staticmethod(_ok)
    )


@pytest.mark.asyncio
async def test_disetujui_kabari_pembuat(monkeypatch, kabar, po):
    _update_status_sukses(monkeypatch)
    hasil = await PurchaseOrderController.update_purchase_order_status(
        55, "approved", user_id=4, user_level=4
    )
    assert hasil == {"message": "ok"}
    assert len(kabar) == 1
    assert kabar[0]["judul"] == "Disetujui"
    assert kabar[0]["ke"] == [10]
    assert "TNT-PO-055" in kabar[0]["pesan"]


@pytest.mark.asyncio
async def test_ditolak_kabari_pembuat(monkeypatch, kabar, po):
    _update_status_sukses(monkeypatch)
    await PurchaseOrderController.update_purchase_order_status(
        55, "cancelled", user_id=4, user_level=4
    )
    assert len(kabar) == 1
    assert kabar[0]["judul"] == "Ditolak"
    assert kabar[0]["ke"] == [10]


@pytest.mark.asyncio
async def test_penyetuju_adalah_pembuat_tidak_dikabari(monkeypatch, kabar, po):
    """Level 5 menyetujui dokumennya sendiri: tidak perlu memberi tahu diri."""
    _update_status_sukses(monkeypatch)
    await PurchaseOrderController.update_purchase_order_status(
        55, "approved", user_id=10, user_level=5
    )
    assert kabar == []


@pytest.mark.asyncio
async def test_kembali_ke_draf_tidak_berkabar(monkeypatch, kabar, po):
    _update_status_sukses(monkeypatch)
    await PurchaseOrderController.update_purchase_order_status(
        55, "draft", user_id=4, user_level=4
    )
    assert kabar == []


@pytest.mark.asyncio
async def test_status_gagal_tidak_berkabar(monkeypatch, kabar, po):
    async def _gagal(pid, status, user_id, user_level=None):
        return {"error": "VALIDATION", "status": 400}

    monkeypatch.setattr(
        modul.PurchaseOrderRepository, "update_status", staticmethod(_gagal)
    )
    await PurchaseOrderController.update_purchase_order_status(
        55, "approved", user_id=4, user_level=4
    )
    assert kabar == []
