"""
Menghapus purchase order: bebas sebelum terbit, hanya pemilik sesudahnya.

Sebelumnya dokumen yang sudah disetujui TIDAK dapat dihapus siapa pun —
ditolak 409 tanpa kecuali. Aturannya kini dilonggarkan atas keputusan
pemilik: yang sudah disetujui tetap tertutup bagi semua orang, kecuali
pemilik sendiri.

Alasan penutupannya tidak berubah. Dokumen yang disetujui sudah dicetak dan
ada di tangan vendor; menghapusnya membuat lembar yang beredar tidak punya
padanan sama sekali di sistem. Yang berubah hanya: kadang dokumen memang
keliru sejak awal dan harus benar-benar hilang, dan yang menanggung
akibatnya bila lembar itu ternyata masih dipakai adalah pemiliknya.

Satu hal yang diuji di sini TIDAK terlihat dari layar mana pun, dan itulah
yang paling perlu dijaga — lihat `test_penghapusan_pemilik_benar_benar_menulis`.
"""

import pytest

from repository.purchase_order_repository import PurchaseOrderRepository
from utils.errors import ErrorCode

PEMILIK = 5      # level 5
MANAJER = 3      # level 3

MODUL = "repository.purchase_order_repository"
AUDIT = "repository.audit_log_repository"


def _siapkan(fake_db, *, disetujui):
    db = fake_db(MODUL, AUDIT)
    db.queue("fetch_one", {"isApproved": 1 if disetujui else 0, "isDelete": 0})
    return db


def _perintah_hapus(db):
    """Perintah UPDATE-nya, bukan pencatatan auditnya.

    Keduanya lewat `execute`, dan yang audit dijalankan BELAKANGAN — memakai
    `last_query("execute")` berarti memeriksa jejak audit dan menyatakan
    lulus atas perintah yang tidak pernah dilihat.
    """
    for metode, kueri in db.calls:
        if metode != "execute":
            continue
        teks = str(kueri)
        if "UPDATE purchase_orders" in teks:
            return teks
    return ""


@pytest.mark.asyncio
async def test_belum_disetujui_bebas_dihapus(fake_db):
    """Termasuk yang sudah diperiksa: dokumennya belum terbit."""
    db = _siapkan(fake_db, disetujui=False)

    hasil = await PurchaseOrderRepository.soft_delete(9, MANAJER, user_level=3)

    assert "error" not in hasil
    assert _perintah_hapus(db), "perintah hapusnya tidak pernah dijalankan"


@pytest.mark.asyncio
async def test_sudah_disetujui_ditolak_bagi_selain_pemilik(fake_db):
    db = _siapkan(fake_db, disetujui=True)

    hasil = await PurchaseOrderRepository.soft_delete(9, MANAJER, user_level=3)

    assert "error" in hasil
    assert hasil["code"] == ErrorCode.PO_DELETE_APPROVED_FORBIDDEN
    assert hasil["status"] == 403
    # Tidak satu pun perubahan sempat ditulis.
    assert db.executed("execute") == 0


@pytest.mark.asyncio
async def test_level_4_TIDAK_boleh(fake_db):
    """Batasnya pemilik, bukan general manager."""
    _siapkan(fake_db, disetujui=True)

    hasil = await PurchaseOrderRepository.soft_delete(9, MANAJER, user_level=4)

    assert hasil["code"] == ErrorCode.PO_DELETE_APPROVED_FORBIDDEN


@pytest.mark.asyncio
async def test_pemilik_boleh_menghapus_yang_sudah_disetujui(fake_db):
    _siapkan(fake_db, disetujui=True)

    hasil = await PurchaseOrderRepository.soft_delete(9, PEMILIK, user_level=5)

    assert "error" not in hasil


@pytest.mark.asyncio
async def test_penghapusan_pemilik_benar_benar_menulis(fake_db):
    """
    Perintahnya tidak boleh membawa saringan `isApproved = 0`.

    Inilah jebakan yang tidak terlihat dari mana pun. Saringan itu ada untuk
    menutup jeda antara pembacaan keadaan dan perintah penghapusan. Bila ia
    ikut terpasang pada penghapusan oleh pemilik, perintahnya tidak
    mencocokkan satu baris pun — dan `execute` yang mengubah NOL baris tidak
    melempar galat apa pun.

    Akibatnya: layar mengabarkan "berhasil dihapus", jejak audit mencatat
    penghapusan, dan dokumennya masih utuh di daftar. Tidak ada satu pun
    tanda bahwa yang terjadi bukan yang dilaporkan.
    """
    db = _siapkan(fake_db, disetujui=True)

    await PurchaseOrderRepository.soft_delete(9, PEMILIK, user_level=5)

    perintah = _perintah_hapus(db)
    assert perintah, "perintah hapusnya tidak pernah dijalankan"
    assert "isApproved" not in perintah, (
        "perintah hapus milik pemilik masih menyaring isApproved — "
        "tidak akan mengubah satu baris pun, dan tidak akan ada galatnya"
    )


@pytest.mark.asyncio
async def test_yang_belum_disetujui_TETAP_disaring_ulang(fake_db):
    """
    Saringannya tidak boleh ikut hilang bagi dokumen biasa.

    Tanpanya, dokumen yang disetujui orang lain di sela antara pembacaan
    keadaan dan perintah ini ikut terhapus — dan yang menghapus mengira ia
    menghapus draf.
    """
    db = _siapkan(fake_db, disetujui=False)

    await PurchaseOrderRepository.soft_delete(9, MANAJER, user_level=3)

    assert "isApproved" in _perintah_hapus(db)


@pytest.mark.asyncio
async def test_dokumen_tidak_ada_tetap_404(fake_db):
    db = fake_db(MODUL, AUDIT)
    db.queue("fetch_one", None)

    hasil = await PurchaseOrderRepository.soft_delete(9, PEMILIK, user_level=5)

    assert hasil["status"] == 404
    assert db.executed("execute") == 0


@pytest.mark.asyncio
async def test_level_kosong_diperlakukan_sebagai_terendah(fake_db):
    """
    Level yang tidak terkirim TIDAK boleh berarti "boleh".

    Rute selalu mengirimkannya, tetapi bawaan yang longgar membuat setiap
    pemanggil baru yang lupa mengirimnya diam-diam melewati aturan ini.
    """
    _siapkan(fake_db, disetujui=True)

    hasil = await PurchaseOrderRepository.soft_delete(9, MANAJER)

    assert hasil["code"] == ErrorCode.PO_DELETE_APPROVED_FORBIDDEN
