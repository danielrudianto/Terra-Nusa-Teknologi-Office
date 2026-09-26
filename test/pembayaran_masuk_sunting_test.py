"""
Pembayaran masuk yang SALAH CATAT harus dapat dibetulkan dan dibatalkan.

Sebelum ini `incoming-payments` hanya punya satu rute: POST. Nomor rekening
yang salah ketik saat mencatat pembayaran faktur penjualan karena itu tidak
dapat dibetulkan sama sekali — barisnya menyebut uang masuk ke rekening yang
tidak pernah menerimanya, selamanya.

Repositorynya sebenarnya SUDAH punya `update` dan `soft_delete`; keduanya
tidak pernah dipanggil dari mana pun. Keduanya juga belum terjaga:

  * `update` menulis apa pun yang dikirim klien, termasuk `isDelete`,
    `isApprove`, dan `salesInvoiceID` — memindahkan pembayaran ke faktur lain
    melewati seluruh penjagaan yang berjalan saat pembayaran dibuat.
  * `soft_delete` tidak pernah mengisi `deletedAt`/`deletedBy`, padahal
    kolomnya ada.

Diuji dengan menjalankan controller YANG SEBENARNYA di atas repository
tiruan: yang dijaga adalah tulisannya benar-benar terjadi (atau benar-benar
ditolak), bukan bahwa kodenya menyebut kata tertentu.
"""

import pytest

from controllers.payment_incoming_controller import PaymentIncomingController
from constants.permission_matrix import MATRIX, ACTIONS


#: Penanda "pakai baris bawaan" — DIBEDAKAN dari `None`, yang di sini berarti
#: "barisnya memang tidak ada".
BAWAAN = object()


class RepoTiruan:
    def __init__(self, baris=BAWAAN):
        self.baris = baris if baris is not BAWAAN else {
            "id": 7,
            "salesInvoiceID": 3,
            "amount": 1_000_000,
            "bankAccountID": 1,
            "isDelete": False,
        }
        self.diubah = []
        self.dihapus = []

    async def get_by_id(self, payment_id):
        return dict(self.baris) if self.baris else None

    async def update(self, payment_id, data, user_id):
        self.diubah.append((payment_id, dict(data), user_id))
        return {"message": "Payment updated successfully"}

    async def soft_delete(self, payment_id, user_id):
        self.dihapus.append((payment_id, user_id))
        return {"message": "Payment deleted successfully"}


@pytest.fixture
def repo(monkeypatch):
    r = RepoTiruan()
    monkeypatch.setattr(
        "controllers.payment_incoming_controller.PaymentIncomingRepository", r
    )
    return r


# ---------------------------------------------------------------- menyunting


@pytest.mark.asyncio
async def test_rekening_salah_dapat_dibetulkan(repo):
    hasil = await PaymentIncomingController.update_payment(
        7, {"bankAccountID": 9}, user_id=4
    )
    assert "error" not in hasil
    assert repo.diubah == [(7, {"bankAccountID": 9}, 4)]


@pytest.mark.asyncio
async def test_tanggal_dan_nominal_juga_boleh(repo):
    hasil = await PaymentIncomingController.update_payment(
        7, {"date": "2026-09-24", "amount": 750_000}, user_id=4
    )
    assert "error" not in hasil
    assert repo.diubah[0][1] == {"date": "2026-09-24", "amount": 750_000}


@pytest.mark.asyncio
async def test_nominal_nol_ditolak(repo):
    # Nol lolos ke pembukuan sebagai penerimaan yang tidak pernah ada, dan
    # membuat fakturnya tampak punya pembayaran padahal tidak.
    hasil = await PaymentIncomingController.update_payment(
        7, {"amount": 0}, user_id=4
    )
    assert hasil["status"] == 400
    assert repo.diubah == []


@pytest.mark.asyncio
async def test_nominal_minus_ditolak(repo):
    hasil = await PaymentIncomingController.update_payment(
        7, {"amount": -5_000}, user_id=4
    )
    assert hasil["status"] == 400
    assert repo.diubah == []


@pytest.mark.asyncio
async def test_nominal_bukan_angka_ditolak(repo):
    hasil = await PaymentIncomingController.update_payment(
        7, {"amount": "seratus ribu"}, user_id=4
    )
    assert hasil["status"] == 400
    assert repo.diubah == []


@pytest.mark.asyncio
async def test_pembayaran_tidak_ada(monkeypatch):
    r = RepoTiruan(baris=None)
    monkeypatch.setattr(
        "controllers.payment_incoming_controller.PaymentIncomingRepository", r
    )
    hasil = await PaymentIncomingController.update_payment(
        7, {"amount": 1}, user_id=4
    )
    assert hasil["status"] == 404


# ------------------------------------------------------------------ menghapus


@pytest.mark.asyncio
async def test_hapus_ditolak_di_bawah_level_4(repo):
    # Yang mencatat (level 3) tidak boleh membatalkan: yang terhapus membuat
    # faktur kembali tampak belum lunas, dan uang yang sudah masuk rekening
    # tidak lagi terlihat di mana pun.
    hasil = await PaymentIncomingController.delete_payment(
        7, user_id=2, user_level=3
    )
    assert hasil["status"] == 403
    assert repo.dihapus == []


@pytest.mark.asyncio
async def test_hapus_tanpa_level_sama_sekali_ditolak(repo):
    # Pemanggil yang lupa meneruskan levelnya tidak boleh menjadi celah.
    hasil = await PaymentIncomingController.delete_payment(7, user_id=2)
    assert hasil["status"] == 403
    assert repo.dihapus == []


@pytest.mark.asyncio
async def test_hapus_boleh_mulai_level_4(repo):
    hasil = await PaymentIncomingController.delete_payment(
        7, user_id=2, user_level=4
    )
    assert "error" not in hasil
    assert repo.dihapus == [(7, 2)]


@pytest.mark.asyncio
async def test_hapus_boleh_level_5(repo):
    hasil = await PaymentIncomingController.delete_payment(
        7, user_id=1, user_level=5
    )
    assert repo.dihapus == [(7, 1)]


# --------------------------------------------------------------------- izin


def test_matriks_izin_selaras_dengan_controller():
    """
    Matriks dan controller harus menyebut level yang SAMA.

    Keduanya menjaga hal yang sama dari dua tempat berbeda; yang satu diubah
    tanpa yang lain adalah bentuk kegagalan yang paling mungkin terjadi di
    sini, dan akibatnya senyap — rutenya mengizinkan, controllernya menolak,
    dan yang memakainya melihat 403 tanpa sebab yang terbaca.
    """
    i = ACTIONS.index("delete")
    assert MATRIX["payment_incoming"][i] == PaymentIncomingController.LEVEL_HAPUS

    # Mencatat tetap level 3 — pekerjaan sehari-hari.
    assert MATRIX["payment_incoming"][ACTIONS.index("create")] == 3
    assert MATRIX["payment_incoming"][ACTIONS.index("update")] == 3
