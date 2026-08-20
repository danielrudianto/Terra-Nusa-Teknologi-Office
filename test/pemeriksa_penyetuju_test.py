"""
Pemeriksa dan penyetuju purchase order harus DUA ORANG.

Dokumen melewati dua tangan dengan sengaja: pemeriksa membaca isinya —
harga, volume, spesifikasi — dan penyetuju memutuskan dokumen itu boleh
terbit.

Sudah terjadi bahwa keduanya jatuh ke satu orang. Dua penjagaan yang ada
sebelumnya keduanya membandingkan dengan PEMBUAT dokumen:

    set_checked   : pembuat tidak boleh memeriksa dokumennya sendiri
    update_status : pembuat tidak boleh menyetujui dokumennya sendiri

Pemeriksa yang bukan pembuat karena itu lolos keduanya. Dari kursi
penggunanya tidak terasa seperti melanggar apa pun: ia menekan "Periksa",
menu itu langsung berganti menampilkan "Setujui", dan ia menekannya. Dua
tahap, satu orang, dua detik.

Diuji lewat repository dengan basis data tiruan — yang diuji ATURANNYA,
bukan mesin basis datanya.
"""

import pytest

from repository.purchase_order_repository import PurchaseOrderRepository
from utils.errors import ErrorCode

PEMBUAT = 1
PEMERIKSA = 2
PENYETUJU = 3

MODUL = "repository.purchase_order_repository"
AUDIT = "repository.audit_log_repository"


def _siapkan(fake_db, *, checked_by, is_checked=1, pembuat=PEMBUAT):
    """Antre balikan yang dibaca `update_status` sebelum menulis apa pun."""
    db = fake_db(MODUL, AUDIT)
    db.queue("fetch_val", pembuat)  # createdBy
    db.queue(
        "fetch_one",
        {"isChecked": is_checked, "checkedBy": checked_by},
    )
    db.queue("fetch_one", {"id": 9, "status": "draft"})  # keadaan sebelum
    return db


@pytest.mark.asyncio
async def test_pemeriksa_tidak_boleh_menyetujui_yang_diperiksanya(fake_db):
    db = _siapkan(fake_db, checked_by=PEMERIKSA)

    hasil = await PurchaseOrderRepository.update_status(
        9, "approved", PEMERIKSA, user_level=4
    )

    assert "error" in hasil
    assert hasil["code"] == ErrorCode.PO_CHECKER_IS_APPROVER
    assert hasil["status"] == 403
    # Dan tidak satu pun perubahan sempat ditulis.
    assert db.executed("execute") == 0


@pytest.mark.asyncio
async def test_orang_lain_tetap_boleh_menyetujui(fake_db):
    """
    Penjagaannya tidak boleh menutup jalur yang benar.

    Aturan yang menolak semua orang sama tidak berguna dengan aturan yang
    menerima semua orang — bedanya yang pertama menghentikan pekerjaan.
    """
    _siapkan(fake_db, checked_by=PEMERIKSA)

    hasil = await PurchaseOrderRepository.update_status(
        9, "approved", PENYETUJU, user_level=4
    )

    assert "error" not in hasil


@pytest.mark.asyncio
async def test_pemilik_dikecualikan(fake_db):
    """
    Level 5 boleh menyetujui yang diperiksanya sendiri.

    Alasannya sama dengan pengecualian pada persetujuan dokumen buatannya
    sendiri: pada akhirnya ialah yang menanggung akibatnya, dan kerap ialah
    satu-satunya yang hadir. Pengecualiannya tetap tercatat pada jejak
    aktivitas.
    """
    _siapkan(fake_db, checked_by=PEMERIKSA)

    hasil = await PurchaseOrderRepository.update_status(
        9, "approved", PEMERIKSA, user_level=5
    )

    assert "error" not in hasil


@pytest.mark.asyncio
async def test_level_4_TIDAK_dikecualikan(fake_db):
    """
    Batasnya 5, bukan 4.

    Level 4 memang berwenang atas seluruh dokumen, tetapi memeriksa lalu
    menyetujui sendiri menghapus satu-satunya mata kedua yang tersisa pada
    dokumen itu.
    """
    _siapkan(fake_db, checked_by=PEMERIKSA)

    hasil = await PurchaseOrderRepository.update_status(
        9, "approved", PEMERIKSA, user_level=4
    )

    assert hasil["code"] == ErrorCode.PO_CHECKER_IS_APPROVER


@pytest.mark.asyncio
async def test_dokumen_lama_tanpa_pemeriksa_tetap_lewat(fake_db):
    """
    `checkedBy` kosong dibiarkan lewat.

    Dokumen yang disetujui sebelum tahap pemeriksaan ada tidak pernah
    mencatat pemeriksanya. Menolaknya berarti menuduh orang yang memang
    tidak diketahui — dan menahan dokumen yang tidak ada cara memperbaikinya.
    """
    _siapkan(fake_db, checked_by=None)

    hasil = await PurchaseOrderRepository.update_status(
        9, "approved", PEMERIKSA, user_level=4
    )

    assert "error" not in hasil


@pytest.mark.asyncio
async def test_belum_diperiksa_tetap_ditolak(fake_db):
    """Aturan lama tidak boleh ikut hilang saat aturan baru ditambahkan."""
    db = _siapkan(fake_db, checked_by=None, is_checked=0)

    hasil = await PurchaseOrderRepository.update_status(
        9, "approved", PENYETUJU, user_level=4
    )

    assert "error" in hasil
    assert hasil["code"] == ErrorCode.VALIDATION
    assert db.executed("execute") == 0


@pytest.mark.asyncio
async def test_pembuat_tetap_tidak_boleh_menyetujui_sendiri(fake_db):
    """Penjagaan yang sudah ada sebelumnya tetap berlaku."""
    db = fake_db(MODUL, AUDIT)
    db.queue("fetch_val", PEMBUAT)  # createdBy = dia sendiri

    hasil = await PurchaseOrderRepository.update_status(
        9, "approved", PEMBUAT, user_level=4
    )

    assert hasil["code"] == ErrorCode.SELF_APPROVAL_FORBIDDEN


@pytest.mark.asyncio
async def test_membatalkan_tidak_ikut_dijaga(fake_db):
    """
    Penjagaannya hanya berlaku pada PERSETUJUAN.

    Menolak atau mengembalikan ke draf justru harus tetap terbuka bagi
    pemeriksanya: dialah yang membaca isinya dan menemukan keliru.
    """
    db = fake_db(MODUL, AUDIT)
    db.queue("fetch_one", {"id": 9, "status": "approved"})

    hasil = await PurchaseOrderRepository.update_status(
        9, "cancelled", PEMERIKSA, user_level=3
    )

    assert "error" not in hasil


@pytest.mark.asyncio
async def test_keadaan_pemeriksaan_dibaca_sekali(fake_db):
    """
    `isChecked` dan `checkedBy` dibaca dalam SATU perjalanan.

    Dua perjalanan terpisah membuka jeda yang di dalamnya pemeriksaannya
    dapat dicabut, dan persetujuannya lolos atas keadaan yang sudah tidak
    berlaku.
    """
    db = _siapkan(fake_db, checked_by=PEMERIKSA)

    await PurchaseOrderRepository.update_status(
        9, "approved", PENYETUJU, user_level=4
    )

    kueri = " ".join(str(q) for m, q in db.calls if m in ("fetch_one", "fetch_val"))
    assert "isChecked" in kueri
    assert "checkedBy" in kueri
