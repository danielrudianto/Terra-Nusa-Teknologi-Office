"""
SPK yang masih menanggung berita acara TIDAK boleh dihapus.

KEJADIAN YANG MELAHIRKAN PENJAGA INI

SPK 145 dihapus sementara empat BAP menggantung di atasnya. Nomornya lalu
dibebaskan menjadi `009-SPK-DPTCC-D~x145` supaya penggantinya dapat terbit di
nomor yang sama — dan keempat BAP itu tetap menunjuk bangkainya. Kepalanya
(`purchaseOrderID`) maupun barisnya (`purchaseOrderItemID`) sama-sama kunci
asing sungguhan; tidak satu pun ikut berpindah.

Akibatnya bukan sekadar tautan putus. Nama pekerjaan pada lembar BAP dibaca
DARI baris SPK, jadi begitu penggantinya memakai nama pekerjaan yang berbeda,
dokumen yang sama mulai mencetak dua nama yang berlainan — dan itu lembar yang
ditandatangani. Baru ketahuan karena nomor `~x145` tampak aneh di layar.

DUA TAUTAN, KEDUANYA DIJAGA

Memeriksa kepala saja tidak cukup: BAP dapat berkepala SPK induk sementara
sebagian barisnya menunjuk baris ADENDUM. Menghapus adendumnya menggantung
baris-baris itu tanpa satu pun kepala yang menyebutkan SPK tersebut.

BERLAKU BAGI SIAPA PUN, PEMILIK SEKALIPUN

Ini bukan pertanyaan "siapa yang berhak" melainkan "apa yang terjadi pada
dokumen lain". Tidak ada jawaban yang membuat penghapusan ini aman selama
BAP-nya masih hidup, jadi tidak ada tingkat wewenang yang melewatinya.
"""

import pytest

from repository.purchase_order_repository import PurchaseOrderRepository
from utils.errors import ErrorCode

MODUL = "repository.purchase_order_repository"


def _kode(hasil) -> str:
    if not isinstance(hasil, dict):
        return ""
    for k in ("code", "error_code"):
        if k in hasil:
            return str(hasil[k])
    g = hasil.get("error")
    if isinstance(g, dict):
        return str(g.get("code", ""))
    return str(g or "")


class TestDitahan:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", [1, 3, 4, 5])
    async def test_ditolak_pada_setiap_level(self, fake_db, level):
        """
        Termasuk level 5. Pemilik boleh menghapus SPK yang sudah disetujui,
        tetapi tidak boleh menggantung berita acara milik orang lain.
        """
        db = fake_db(MODUL)
        db.queue("fetch_one", {"isApproved": 1, "isDelete": 0})
        db.queue("fetch_one", {"jumlah": 4, "contoh": "001-925-DPTCC-2026"})

        hasil = await PurchaseOrderRepository.soft_delete(
            purchase_order_id=145, user_id=1, user_level=level
        )

        assert hasil.get("status") == 409
        assert _kode(hasil) == ErrorCode.PO_DELETE_HAS_COP

    @pytest.mark.asyncio
    async def test_pesannya_menyebut_jumlah_dan_contoh(self, fake_db):
        """
        Yang membacanya harus tahu APA yang harus dikerjakan, bukan sekadar
        bahwa ia ditolak — jumlahnya, satu nomor untuk dicari, dan jalan
        keluarnya.
        """
        db = fake_db(MODUL)
        db.queue("fetch_one", {"isApproved": 0, "isDelete": 0})
        db.queue("fetch_one", {"jumlah": 4, "contoh": "001-925-DPTCC-2026"})

        hasil = await PurchaseOrderRepository.soft_delete(
            purchase_order_id=145, user_id=1, user_level=5
        )

        pesan = str(hasil.get("message") or hasil.get("error") or hasil)
        assert "4" in pesan
        assert "001-925-DPTCC-2026" in pesan
        assert "batalkan" in pesan.lower()

    @pytest.mark.asyncio
    async def test_tidak_ada_penulisan_sebelum_penolakan(self, fake_db):
        """
        Ditolak SEBELUM `UPDATE` mana pun. Antrean `execute` sengaja kosong:
        bila penjaganya lolos, pengujian ini gagal karena repository menyentuh
        basis data — bukan karena assert di bawah.
        """
        db = fake_db(MODUL)
        db.queue("fetch_one", {"isApproved": 0, "isDelete": 0})
        db.queue("fetch_one", {"jumlah": 1, "contoh": "001-X"})

        await PurchaseOrderRepository.soft_delete(
            purchase_order_id=145, user_id=1, user_level=5
        )

        assert db.executed("execute") == 0


class TestDilewatkan:
    @pytest.mark.asyncio
    async def test_tanpa_cop_tetap_boleh_dihapus(self, fake_db):
        """Draf tanpa berita acara tidak disentuh penjaga ini sama sekali."""
        db = fake_db(MODUL)
        db.queue("fetch_one", {"isApproved": 0, "isDelete": 0})
        db.queue("fetch_one", {"jumlah": 0, "contoh": None})
        db.queue("execute", 1)

        hasil = await PurchaseOrderRepository.soft_delete(
            purchase_order_id=900, user_id=1, user_level=3
        )

        assert _kode(hasil) != ErrorCode.PO_DELETE_HAS_COP

    @pytest.mark.asyncio
    async def test_cop_yang_sudah_dibatalkan_tidak_menahan(self, fake_db):
        """
        Penjaganya menghitung `c.isDelete = 0` saja. BAP yang sudah dibatalkan
        memang tidak lagi menunjuk apa pun yang berarti — menahannya berarti
        SPK keliru tidak pernah dapat dibersihkan.
        """
        db = fake_db(MODUL)
        db.queue("fetch_one", {"isApproved": 0, "isDelete": 0})
        db.queue("fetch_one", {"jumlah": 0, "contoh": None})
        db.queue("execute", 1)

        hasil = await PurchaseOrderRepository.soft_delete(
            purchase_order_id=145, user_id=1, user_level=3
        )

        assert hasil.get("status") != 409

    @pytest.mark.asyncio
    async def test_dokumen_tidak_ada_tetap_404(self, fake_db):
        """Penjaga baru tidak boleh mendahului pemeriksaan keberadaan."""
        db = fake_db(MODUL)
        db.queue("fetch_one", None)

        hasil = await PurchaseOrderRepository.soft_delete(
            purchase_order_id=99999, user_id=1, user_level=5
        )

        assert hasil.get("status") == 404


class TestKuerinya:
    @pytest.mark.asyncio
    async def test_memeriksa_kepala_DAN_baris(self, fake_db):
        """
        Kedua tautan disebut dalam satu kueri. Memeriksa kepalanya saja
        melewatkan BAP yang barisnya menunjuk baris adendum SPK ini.
        """
        db = fake_db(MODUL)
        db.queue("fetch_one", {"isApproved": 0, "isDelete": 0})
        db.queue("fetch_one", {"jumlah": 0, "contoh": None})
        db.queue("execute", 1)

        await PurchaseOrderRepository.soft_delete(
            purchase_order_id=145, user_id=1, user_level=3
        )

        kueri = " ".join(str(q) for m, q in db.calls if m == "fetch_one")
        assert "c.purchaseOrderID = :id" in kueri
        assert "certificate_of_payment_items" in kueri
        assert "poi.purchaseOrderID = :id" in kueri
        # Yang sudah dibatalkan tidak ikut dihitung.
        assert "c.isDelete = 0" in kueri
