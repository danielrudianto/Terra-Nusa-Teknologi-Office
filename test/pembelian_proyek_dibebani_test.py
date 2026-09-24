"""
Pembelian dapat DIBEBANKAN ke proyek lain daripada purchase order-nya.

Dahulu kolomnya selalu dibuang: proyek hanya boleh bergerak mengikuti nomor
PO. Alasannya benar — bila keduanya boleh berbeda diam-diam, rekap per
proyek menghitung pembelian di proyek yang berbeda dari PO-nya, dan tidak
ada yang tahu mana yang benar.

Tetapi aturan itu mengunci keadaan yang nyata: sebagian PO memang tidak
dapat diterbitkan atas nama proyek yang membiayainya. Tanpa jalan keluar,
satu-satunya cara membetulkannya adalah menghapus pembeliannya dan mencatat
ulang.

Yang menjawab keberatan lama bukan melarangnya, melainkan membuatnya
TERLIHAT: pembelian menyimpan proyeknya sendiri — satu sumber untuk seluruh
rekap biaya — dan perbedaannya dari PO-nya dicatat pada jejak.
"""

import pytest

import controllers.purchase_controller as modul
from controllers.purchase_controller import PurchaseController


PEMBELIAN = {
    "id": 5,
    "purchaseOrderName": "144-PO-R501-G",
    "projectName": "R501",
    "dpp": 1_000_000,
    "ppn": 11,
    "pphPercentage": 0,
}


class RepoPembelian:
    diperbarui = None

    @staticmethod
    async def get_by_id(_id):
        return dict(PEMBELIAN)

    @staticmethod
    async def update(purchase_id, data, user_id):
        RepoPembelian.diperbarui = (purchase_id, dict(data), user_id)
        return {"message": "Purchase updated successfully"}


class RepoPo:
    @staticmethod
    async def cari_aktif_berdasarkan_nama(nama):
        peta = {
            "144-PO-R501-G": {"name": "144-PO-R501-G", "projectName": "R501"},
            "021-PO-TSKBP-G": {"name": "021-PO-TSKBP-G", "projectName": "TSKBP"},
        }
        return peta.get(nama)


class RepoProyek:
    @staticmethod
    async def get_by_code(kode):
        return {"code": kode.upper()} if kode.upper() in {"R501", "MCHP", "TSKBP"} else None


class RepoBayar:
    @staticmethod
    async def hitung_pembayaran_aktif(_id):
        return 0


class Audit:
    baris = []

    @staticmethod
    async def record(**kw):
        Audit.baris.append(kw)

    @staticmethod
    def diff(a, b):
        return {}


@pytest.fixture(autouse=True)
def pasang(monkeypatch):
    RepoPembelian.diperbarui = None
    Audit.baris = []
    monkeypatch.setattr(modul, "PurchaseRepository", RepoPembelian)
    monkeypatch.setattr(modul, "PurchaseOrderRepository", RepoPo)
    monkeypatch.setattr(modul, "ProjectRepository", RepoProyek)
    monkeypatch.setattr(modul, "PaymentOutgoingRepository", RepoBayar)
    import repository.audit_log_repository as mod_audit

    monkeypatch.setattr(mod_audit, "AuditLogRepository", Audit)


async def sunting(data):
    return await PurchaseController.update_purchase_meta(5, data, userID=1, userLevel=5)


@pytest.mark.asyncio
async def test_proyek_dapat_diganti_sendiri():
    hasil = await sunting({"projectName": "MCHP"})
    assert "error" not in hasil
    assert RepoPembelian.diperbarui[1]["projectName"] == "MCHP"


@pytest.mark.asyncio
async def test_perbedaan_dari_po_dicatat_pada_jejak():
    await sunting({"projectName": "MCHP"})
    jejak = [b for b in Audit.baris if b.get("action") == "purchase_project_override"]
    assert len(jejak) == 1
    assert "MCHP" in jejak[0]["note"]
    assert "144-PO-R501-G" in jejak[0]["note"]


@pytest.mark.asyncio
async def test_sama_dengan_po_tidak_menimbulkan_jejak_tambahan():
    # Bukan penyimpangan; mencatatnya hanya menambah baris yang tidak
    # menyatakan apa pun.
    await sunting({"projectName": "R501"})
    assert [b for b in Audit.baris if b.get("action") == "purchase_project_override"] == []


@pytest.mark.asyncio
async def test_proyek_yang_tidak_ada_ditolak():
    # Kolomnya TEKS, bukan tautan: tidak ada penjaga basis data yang
    # menolak proyek yang tidak pernah ada.
    hasil = await sunting({"projectName": "TIDAKADA"})
    assert hasil["status"] == 400
    assert RepoPembelian.diperbarui is None


@pytest.mark.asyncio
async def test_proyek_kosong_ditolak():
    hasil = await sunting({"projectName": "   "})
    assert hasil["status"] == 400
    assert RepoPembelian.diperbarui is None


@pytest.mark.asyncio
async def test_ganti_nomor_po_tetap_memindahkan_proyeknya():
    # Perilaku lama tidak boleh hilang: tanpa proyek yang disebut sendiri,
    # proyeknya mengikuti PO barunya.
    hasil = await sunting({"purchaseOrderName": "021-PO-TSKBP-G"})
    assert "error" not in hasil
    assert RepoPembelian.diperbarui[1]["projectName"] == "TSKBP"
    assert [b for b in Audit.baris if b.get("action") == "purchase_project_override"] == []


@pytest.mark.asyncio
async def test_proyek_yang_disebut_mengalahkan_proyek_po_barunya():
    hasil = await sunting(
        {"purchaseOrderName": "021-PO-TSKBP-G", "projectName": "MCHP"}
    )
    assert "error" not in hasil
    assert RepoPembelian.diperbarui[1]["projectName"] == "MCHP"
    jejak = [b for b in Audit.baris if b.get("action") == "purchase_project_override"]
    assert len(jejak) == 1
    assert "021-PO-TSKBP-G" in jejak[0]["note"]


@pytest.mark.asyncio
async def test_menyunting_hal_lain_tidak_menyentuh_proyek():
    hasil = await sunting({"invoiceName": "INV-77"})
    assert "error" not in hasil
    assert "projectName" not in RepoPembelian.diperbarui[1]
