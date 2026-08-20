"""
Mencabut pemeriksaan purchase order.

MEMBERI centang dan MENCABUTNYA bukan dua arah dari satu tindakan yang sama.

Memberi centang adalah menyatakan "saya sudah membaca isinya dan isinya
benar" — pernyataan atas nama sendiri, dan setiap pemeriksa berhak
membuatnya. Mencabut centang ORANG LAIN menghapus pernyataan orang lain, dan
di sistem ini ia sekaligus MENGGUGURKAN PERSETUJUAN yang terlanjur terbit:
`isApproved` dikembalikan False dan statusnya kembali "draft".

Artinya, sebelum penjagaan ini ada, satu klik dari siapa pun yang berizin
`purchase_order:update` dapat membatalkan tanda tangan seorang direktur tanpa
dokumen itu berubah satu huruf pun. Yang menandatanganinya tidak diberi tahu,
dan dari layar mana pun tidak tampak apa yang terjadi — yang tersisa hanya
dokumen yang tiba-tiba kembali ke antrean.

Yang paling perlu dijaga di berkas ini: penolakannya harus terjadi SEBELUM
perintah UPDATE berjalan. Penjagaan yang benar tetapi terlambat tidak
menyelamatkan apa pun.
"""

import pytest

from repository.purchase_order_repository import PurchaseOrderRepository
from utils.errors import ErrorCode
from utils.permission import boleh_mencabut_pemeriksaan

PEMERIKSA = 7          # yang mencentang dokumennya
ORANG_LAIN = 9         # pemeriksa lain, level sama
MODUL = "repository.purchase_order_repository"
AUDIT = "repository.audit_log_repository"


def _siapkan(fake_db, *, sudah_diperiksa=True, oleh=PEMERIKSA):
    db = fake_db(MODUL, AUDIT)
    # Bacaan penjaga: keadaan pemeriksaan dokumennya.
    db.queue(
        "fetch_one",
        {"isChecked": 1 if sudah_diperiksa else 0, "checkedBy": oleh},
        # `_sebelum`, lalu bacaan sesudah untuk jejak audit.
        {"id": 5, "isChecked": 1},
        {"id": 5, "isChecked": 0},
    )
    return db


def _perintah_ubah(db) -> str:
    """Perintah UPDATE-nya sendiri, bukan pencatatan auditnya."""
    for metode, kueri in db.calls:
        if metode == "execute" and "UPDATE purchase_orders" in str(kueri):
            return str(kueri)
    return ""


# ---------------------------------------------------------------------
# Aturannya sendiri.
# ---------------------------------------------------------------------


def test_pemeriksanya_sendiri_boleh():
    """
    Yang menemukan kekeliruan SESUDAH mencentang harus punya jalan
    membetulkannya. Tanpa itu ia akan diam saja, dan diamnya lebih mahal
    daripada pencabutannya.
    """
    assert boleh_mencabut_pemeriksaan(3, adalah_pemeriksa=True) is True
    assert boleh_mencabut_pemeriksaan(1, adalah_pemeriksa=True) is True


def test_level_empat_boleh_atas_siapa_pun():
    assert boleh_mencabut_pemeriksaan(4, adalah_pemeriksa=False) is True
    assert boleh_mencabut_pemeriksaan(5, adalah_pemeriksa=False) is True


def test_pemeriksa_lain_tidak_boleh():
    """Level 3 yang berhak MEMERIKSA tetap tidak berhak MENCABUT punya orang."""
    assert boleh_mencabut_pemeriksaan(3, adalah_pemeriksa=False) is False


def test_level_tidak_terbaca_jatuh_ke_yang_paling_sedikit_haknya():
    """Bukan lolos: level yang tidak dikenali harus ditolak, bukan diloloskan."""
    assert boleh_mencabut_pemeriksaan(None) is False
    assert boleh_mencabut_pemeriksaan("empat") is False
    assert boleh_mencabut_pemeriksaan("") is False


# ---------------------------------------------------------------------
# Penerapannya di repository.
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pemeriksa_lain_ditolak_sebelum_menulis(fake_db):
    """
    Yang diuji BUKAN hanya balikan galatnya.

    Penjagaan yang menolak sesudah UPDATE berjalan tetap menggugurkan
    persetujuannya — dokumennya sudah kembali menjadi draf, dan galat yang
    muncul di layar tidak mengembalikannya.
    """
    db = _siapkan(fake_db, oleh=PEMERIKSA)

    hasil = await PurchaseOrderRepository.set_checked(
        5, False, ORANG_LAIN, user_level=3
    )

    assert "error" in hasil
    assert hasil.get("code") == ErrorCode.FORBIDDEN or "error" in hasil
    assert hasil.get("status") == 403
    assert not _perintah_ubah(db), "dokumennya terlanjur diubah sebelum ditolak"


@pytest.mark.asyncio
async def test_pemeriksanya_sendiri_menulis(fake_db):
    db = _siapkan(fake_db, oleh=PEMERIKSA)

    hasil = await PurchaseOrderRepository.set_checked(
        5, False, PEMERIKSA, user_level=3
    )

    assert "error" not in hasil
    assert _perintah_ubah(db), "pencabutannya tidak pernah dijalankan"


@pytest.mark.asyncio
async def test_level_empat_menulis(fake_db):
    db = _siapkan(fake_db, oleh=PEMERIKSA)

    hasil = await PurchaseOrderRepository.set_checked(
        5, False, ORANG_LAIN, user_level=4
    )

    assert "error" not in hasil
    assert _perintah_ubah(db)


@pytest.mark.asyncio
async def test_dokumen_yang_belum_diperiksa_tidak_dijaga(fake_db):
    """
    Mencabut sesuatu yang tidak ada bukan pencabutan.

    Menolaknya hanya menghasilkan galat pada tombol yang tidak melakukan
    apa-apa — dan galat tanpa sebab yang terlihat membuat orang berhenti
    memakai layarnya.
    """
    db = _siapkan(fake_db, sudah_diperiksa=False, oleh=None)

    hasil = await PurchaseOrderRepository.set_checked(
        5, False, ORANG_LAIN, user_level=1
    )

    assert "error" not in hasil
    assert _perintah_ubah(db)


@pytest.mark.asyncio
async def test_mencentang_tidak_ikut_dipersempit(fake_db):
    """
    Aturan ini hanya untuk MENCABUT.

    Ikut mempersempit pemberian centang berarti pemeriksaan berhenti sama
    sekali begitu satu orang cuti — dan itu masalah yang lebih besar daripada
    yang sedang dibetulkan.
    """
    db = fake_db(MODUL, AUDIT)
    db.queue("fetch_val", None)  # pembuatnya, untuk penjaga periksa-sendiri
    db.queue("fetch_one", {"id": 5, "isChecked": 0}, {"id": 5, "isChecked": 1})

    hasil = await PurchaseOrderRepository.set_checked(
        5, True, ORANG_LAIN, user_level=3, departments={"procurement"}
    )

    assert "error" not in hasil
    assert _perintah_ubah(db)


def test_pencabutan_masih_menggugurkan_persetujuan():
    """
    Sebab aturan ini ada sama sekali.

    Bila pencabutan kelak berhenti menggugurkan persetujuan, penjagaan di
    atas boleh dilonggarkan — tetapi keduanya harus berubah bersama, dan
    pengujian ini yang memaksanya ketahuan.
    """
    import os

    akar = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    isi = open(
        os.path.join(akar, "repository", "purchase_order_repository.py")
    ).read()
    blok = isi[isi.index("async def set_checked(") :]
    blok = blok[: blok.find("\n    @staticmethod")]

    assert '"isApproved": False' in blok
    assert '"status": "draft"' in blok
