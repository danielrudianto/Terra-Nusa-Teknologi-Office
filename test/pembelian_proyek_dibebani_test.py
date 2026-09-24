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
    "purchaseType": "6.4.2",
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
            "144-PO-R501-G": {
                "name": "144-PO-R501-G",
                "projectName": "R501",
                "purchaseType": "G",
            },
            "021-PO-TSKBP-G": {
                "name": "021-PO-TSKBP-G",
                "projectName": "TSKBP",
                "purchaseType": "G",
            },
            "831-SPK-PUSAT-6.4.1": {
                "name": "831-SPK-PUSAT-6.4.1",
                "projectName": "PUSAT",
                "purchaseType": "6.4.1",
            },
        }
        return peta.get(nama)


class RepoProyek:
    @staticmethod
    async def get_by_code(kode):
        return {"code": kode.upper()} if kode.upper() in {"R501", "MCHP", "TSKBP", "PUSAT"} else None


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


# ------------------------------------------- jenis pengadaan ikut PO-nya


@pytest.mark.asyncio
async def test_jenis_pengadaan_ikut_nomor_po_barunya():
    """
    `purchaseType` menentukan KATEGORI biaya pada laporan proyek.

    Kasus nyatanya: nomor PO salah diketik saat mencatat, lalu dibetulkan.
    Proyeknya ikut berpindah, jenisnya tidak — sehingga pembelian jasa
    hukum tetap terhitung sebagai asuransi, dan yang membaca laporan
    mencari nilai yang "hilang" di kategori yang benar sementara angkanya
    ada di kategori lain. Tidak ada galat sama sekali.
    """
    hasil = await sunting({"purchaseOrderName": "831-SPK-PUSAT-6.4.1"})
    assert "error" not in hasil
    assert RepoPembelian.diperbarui[1]["purchaseType"] == "6.4.1"
    assert RepoPembelian.diperbarui[1]["projectName"] == "PUSAT"


@pytest.mark.asyncio
async def test_jenis_tidak_disentuh_bila_nomor_po_tidak_berubah():
    # Penyuntingan nomor faktur tidak boleh menulis ulang kolom yang tidak
    # ada hubungannya.
    hasil = await sunting({"invoiceName": "INV-77"})
    assert "error" not in hasil
    assert "purchaseType" not in RepoPembelian.diperbarui[1]


@pytest.mark.asyncio
async def test_jenis_dari_layar_tidak_dipercaya():
    # Muatan dapat disusun sendiri lewat Network tab; jenisnya selalu
    # diambil dari dokumen PO-nya, bukan dari yang dikirim.
    hasil = await sunting(
        {"purchaseOrderName": "831-SPK-PUSAT-6.4.1", "purchaseType": "F"}
    )
    assert "error" not in hasil
    assert RepoPembelian.diperbarui[1]["purchaseType"] == "6.4.1"


# =====================================================================
# JALUR KEDUA: PUT /purchases/update
#
# Lubang yang sama pernah ada di sini, dan justru inilah jalur yang
# dipakai layar "Ubah Pembelian" — sementara pemeriksaannya hanya ada di
# `update_purchase_meta`. Pemilih proyek di layar itu SENGAJA menerima
# kode asing dengan peringatan, bukan menolaknya, sehingga satu huruf
# salah ketik cukup untuk melenyapkan pembelian dari Laporan Proyek.
# =====================================================================


async def ubah(data):
    return await PurchaseController.update_purchase(5, data, userID=1, userLevel=5)


@pytest.mark.asyncio
async def test_ubah_menolak_proyek_yang_tidak_ada():
    hasil = await ubah({"projectName": "MICZ2"})
    assert hasil["status"] == 400
    assert RepoPembelian.diperbarui is None


@pytest.mark.asyncio
async def test_ubah_menerima_proyek_yang_ada():
    hasil = await ubah({"projectName": "mchp"})
    assert "error" not in hasil
    # Dinormalkan ke kode resminya, bukan disimpan apa adanya.
    assert RepoPembelian.diperbarui[1]["projectName"] == "MCHP"


@pytest.mark.asyncio
async def test_ubah_menolak_nomor_po_yang_tidak_ada():
    hasil = await ubah({"purchaseOrderName": "999-PO-XXX-F"})
    assert hasil["status"] == 400
    assert RepoPembelian.diperbarui is None


@pytest.mark.asyncio
async def test_ubah_memindahkan_proyek_dan_jenis_bersama_nomor_po():
    hasil = await ubah({"purchaseOrderName": "831-SPK-PUSAT-6.4.1"})
    assert "error" not in hasil
    assert RepoPembelian.diperbarui[1]["projectName"] == "PUSAT"
    assert RepoPembelian.diperbarui[1]["purchaseType"] == "6.4.1"


@pytest.mark.asyncio
async def test_ubah_tidak_menyentuh_proyek_bila_tidak_dikirim():
    hasil = await ubah({"invoiceName": "INV-88"})
    assert "error" not in hasil
    assert "projectName" not in RepoPembelian.diperbarui[1]
    assert "purchaseType" not in RepoPembelian.diperbarui[1]


# =====================================================================
# STATUS LUNAS DIHITUNG ULANG KETIKA NILAINYA BERGESER
#
# `isPaid` adalah kesimpulan: nilai dokumen dibanding pembayaran yang
# sudah disetujui. Sampai sekarang hanya sisi PEMBAYARAN yang memicunya,
# sehingga dokumen yang nilainya dinaikkan level 4 setelah lunas tetap
# bertanda lunas — dan hilang dari kartu jatuh tempo tujuh hari, yang
# menyaring `isPaid = 0`.
# =====================================================================


@pytest.mark.asyncio
async def test_menaikkan_nilai_memicu_hitung_ulang_lunas(monkeypatch):
    dipanggil = []

    class Bayar:
        @staticmethod
        async def hitung_pembayaran_aktif(_id):
            return 1

    class Keluar:
        @staticmethod
        async def selaraskan_status_lunas(penagih, userID=None, konfirmasi=False):
            dipanggil.append((penagih.purchaseID, userID))

    monkeypatch.setattr(modul, "PaymentOutgoingRepository", Bayar)
    import controllers.payment_outgoing_controller as mod_keluar

    monkeypatch.setattr(mod_keluar, "PaymentOutgoingController", Keluar)

    hasil = await PurchaseController.update_purchase(
        5, {"dpp": 1_200_000}, userID=9, userLevel=5
    )
    assert "error" not in hasil
    # Penagihnya harus menunjuk pembelian ini, bukan None — kelas bersarang
    # yang membaca variabel fungsinya melempar NameError, dan galat itu
    # ditelan sehingga perhitungannya diam-diam tidak pernah berjalan.
    assert dipanggil == [(5, 9)]


@pytest.mark.asyncio
async def test_menyunting_selain_nilai_tidak_memicu_hitung_ulang(monkeypatch):
    dipanggil = []

    class Keluar:
        @staticmethod
        async def selaraskan_status_lunas(penagih, userID=None, konfirmasi=False):
            dipanggil.append(penagih.purchaseID)

    import controllers.payment_outgoing_controller as mod_keluar

    monkeypatch.setattr(mod_keluar, "PaymentOutgoingController", Keluar)

    hasil = await PurchaseController.update_purchase(
        5, {"invoiceName": "INV-99"}, userID=9, userLevel=5
    )
    assert "error" not in hasil
    assert dipanggil == []
