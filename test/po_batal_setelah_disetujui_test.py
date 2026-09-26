"""
Membatalkan purchase order yang SUDAH DISETUJUI — hanya pemilik.

KENAPA INI PERLU DIUJI SENDIRI

Seluruh penjagaan di `update_status` bersyarat `status == "approved"`:
persetujuan-sendiri, "harus sudah diperiksa", pemeriksa-bukan-penyetuju, dan
penyempitan `WHERE` untuk lomba. Tidak satu pun berlaku pada cabang yang
lain. Sementara itu cabang yang lain MENULIS:

    isApproved = False, approvedBy = None, approvedAt = None

Artinya siapa pun yang memegang `purchase_order:approve` — level 3 ke atas —
dapat mencabut persetujuan purchase order yang sudah terbit dan dipegang
vendor, tanpa satu pun galat. Layar desktop menyembunyikan tombolnya begitu
dokumennya selesai, jadi dari sana tidak pernah terlihat; rutenya sendiri
tetap terbuka.

Aturannya disamakan dengan MENGHAPUS yang sudah disetujui — hanya pemilik
(level 5) — karena akibatnya memang sama.
"""

import pytest

from repository.purchase_order_repository import PurchaseOrderRepository
from utils.errors import ErrorCode

MODULE = "repository.purchase_order_repository"


def _kode(hasil) -> str:
    """Kode galat, apa pun bentuk pembungkus `app_error` yang dipakai."""
    if not isinstance(hasil, dict):
        return ""
    for kunci in ("code", "error_code"):
        if kunci in hasil:
            return str(hasil[kunci])
    galat = hasil.get("error")
    if isinstance(galat, dict):
        return str(galat.get("code", ""))
    return str(galat or "")


class TestBatalkanYangSudahDisetujui:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", ["cancelled", "draft", "completed"])
    @pytest.mark.parametrize("level", [1, 2, 3, 4])
    async def test_ditolak_di_bawah_pemilik(self, fake_db, status, level):
        """
        PO yang sudah disetujui tidak dapat dibatalkan — atau dikembalikan ke
        draf, atau ditandai selesai — oleh siapa pun di bawah level 5.

        `fetch_val` pertama adalah pembacaan `isApproved` milik penjaga baru.
        Penolakannya harus terjadi SEBELUM satu pun penulisan, jadi tidak ada
        `execute` yang diantrekan sama sekali: kalau penjaganya lolos,
        pengujian ini gagal karena antreannya habis, bukan karena assert.
        """
        db = fake_db(MODULE)
        db.queue("fetch_val", 1)  # isApproved = 1

        hasil = await PurchaseOrderRepository.update_status(
            purchase_order_id=7,
            status=status,
            user_id=99,
            user_level=level,
        )

        assert _kode(hasil) == ErrorCode.PO_CANCEL_APPROVED_FORBIDDEN
        assert hasil.get("status") == 403

    @pytest.mark.asyncio
    async def test_yang_belum_disetujui_tetap_bebas_dibatalkan(self, fake_db):
        """
        Draf tidak disentuh sama sekali: membatalkannya tetap boleh bagi
        siapa pun yang berhak menyetujui. Penjaga baru hanya membaca
        `isApproved`, mendapat 0, dan meneruskan.
        """
        db = fake_db(MODULE)
        db.queue("fetch_val", 0)  # isApproved = 0
        db.queue("fetch_one", {"id": 7, "isApproved": 0, "status": "draft"})
        db.queue("execute", 1)

        hasil = await PurchaseOrderRepository.update_status(
            purchase_order_id=7,
            status="cancelled",
            user_id=99,
            user_level=3,
        )

        assert _kode(hasil) != ErrorCode.PO_CANCEL_APPROVED_FORBIDDEN

    @pytest.mark.asyncio
    async def test_pemilik_boleh(self, fake_db):
        """
        Level 5 lewat. Kadang dokumennya memang keliru sejak awal, dan yang
        memutuskan itu pemiliknya — sama persis dengan aturan menghapus.
        """
        db = fake_db(MODULE)
        db.queue("fetch_val", 1)  # isApproved = 1
        db.queue("fetch_one", {"id": 7, "isApproved": 1, "status": "approved"})
        db.queue("execute", 1)

        hasil = await PurchaseOrderRepository.update_status(
            purchase_order_id=7,
            status="cancelled",
            user_id=99,
            user_level=5,
        )

        assert _kode(hasil) != ErrorCode.PO_CANCEL_APPROVED_FORBIDDEN

    @pytest.mark.asyncio
    async def test_menyetujui_tidak_ikut_terkena(self, fake_db):
        """
        Penjaga baru hanya untuk `status != "approved"`. Jalur persetujuan
        punya penjaganya sendiri dan tidak boleh berubah perilakunya — di
        sini yang menolak `PO_ALREADY_APPROVED`, bukan penjaga pembatalan.
        """
        db = fake_db(MODULE)
        # Tidak ada pembacaan `isApproved` milik penjaga pembatalan:
        # antrean langsung dipakai penjaga persetujuan yang lama.
        db.queue("fetch_val", 40)  # createdBy, untuk penjaga setuju-sendiri
        db.queue(
            "fetch_one",
            {"isChecked": 1, "checkedBy": 41, "isApproved": 1},
        )

        hasil = await PurchaseOrderRepository.update_status(
            purchase_order_id=7,
            status="approved",
            user_id=99,
            user_level=3,
        )

        assert _kode(hasil) == ErrorCode.PO_ALREADY_APPROVED
