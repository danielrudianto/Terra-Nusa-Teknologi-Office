"""
Tahap yang sudah dilewati tidak dikerjakan ulang.

KELAS KEGAGALAN YANG DIJAGA

Ini ditemukan di produksi, bukan di sini: beberapa orang menekan "Periksa"
pada purchase order yang SUDAH diperiksa, berkali-kali, dan setiap kali
berhasil. Tidak ada galat, tidak ada yang merah, dan daftar di layar tidak
berubah tampilannya.

Yang terjadi diam-diam: `checkedBy` dan `checkedAt` pemeriksa pertama
DITIMPA. Pada dokumen yang sudah disetujui, hasilnya `checkedAt` yang lebih
baru daripada `approvedAt` — jejak yang menyatakan dokumen itu diperiksa
SESUDAH disetujui, yang tidak mungkin dan tidak akan pernah disebut siapa
pun.

Sebabnya cabang `checked=True` di `set_checked` tidak membaca keadaan
dokumennya sama sekali, dan UPDATE-nya hanya bersyarat `id`:

    UPDATE purchase_orders SET isChecked=1, checkedBy=:u, checkedAt=:t
     WHERE id = :id

Pemicunya bahkan tidak perlu dua orang berbarengan: cukup daftar di layar
seseorang yang sudah basi. Frontend memang menyembunyikan "Periksa" bila
`po.isChecked`, tetapi nilai itu dibaca dari halaman yang dimuat sebelum
orang lain memeriksa.

DUA LAPIS, DAN KEDUANYA DIUJI

  1. Pembacaan keadaan di awal — supaya pesannya dapat menyebut SIAPA yang
     sudah memeriksa. Ini saja tidak cukup: dua permintaan berbarengan
     sama-sama lolos pembacaan itu.
  2. Syarat keadaan di dalam WHERE — ini penjaga yang sebenarnya. Basis data
     menerapkannya satu per satu, jadi yang kedua tidak menemukan baris yang
     cocok.

Pengujian di bawah memeriksa keduanya TERPISAH, karena lapis pertama yang
lulus dapat menutupi lapis kedua yang hilang.
"""

import pytest

from repository.purchase_order_repository import PurchaseOrderRepository
from utils.errors import ErrorCode

MODUL = "repository.purchase_order_repository"
AUDIT = "repository.audit_log_repository"

PEMBUAT = 1
PEMERIKSA_PERTAMA = 2
ORANG_KEDUA = 7


def _dokumen(**ubah):
    d = {
        "id": 9,
        "createdBy": PEMBUAT,
        "isChecked": 0,
        "checkedBy": None,
        "isApproved": 0,
    }
    d.update(ubah)
    return d


def _siapkan(fake_db, sebelum, *, sesudah=None):
    db = fake_db(MODUL, AUDIT)
    db.queue("fetch_one", sebelum, sesudah or _dokumen(isChecked=1))
    return db


def _perintah_ubah(db):
    """UPDATE atas purchase_orders sendiri, bukan pencatatan auditnya."""
    return [
        str(q)
        for m, q in db.calls
        if m == "execute" and str(q).startswith("UPDATE purchase_orders")
    ]


async def _periksa(db_user=ORANG_KEDUA):
    return await PurchaseOrderRepository.set_checked(
        9, True, db_user, user_level=3, departments={"procurement"}
    )


# ---------------------------------------------------------------------
# Lapis 1: keadaan dibaca, dan penolakannya menyebut sebabnya.
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dokumen_yang_sudah_diperiksa_ditolak(fake_db):
    db = _siapkan(fake_db, _dokumen(isChecked=1, checkedBy=PEMERIKSA_PERTAMA))
    db.queue("fetch_val", "Budi Santoso")  # nama pemeriksa pertama

    hasil = await _periksa()

    assert hasil["code"] == ErrorCode.PO_ALREADY_CHECKED
    assert hasil["status"] == 409
    assert not _perintah_ubah(db), (
        "dokumennya terlanjur ditulis sebelum ditolak — `checkedBy` "
        "pemeriksa pertama sudah hilang pada saat galatnya muncul"
    )


@pytest.mark.asyncio
async def test_penolakannya_menyebut_nama_pemeriksanya(fake_db):
    """
    "Sudah diperiksa" saja tidak memberi tahu langkah berikutnya.

    Yang membacanya perlu tahu kepada siapa ia bertanya bila menurutnya
    pemeriksaan itu keliru.
    """
    db = _siapkan(fake_db, _dokumen(isChecked=1, checkedBy=PEMERIKSA_PERTAMA))
    db.queue("fetch_val", "Budi Santoso")

    hasil = await _periksa()

    assert "Budi Santoso" in hasil["error"]


@pytest.mark.asyncio
async def test_nama_pemeriksa_tidak_dibaca_pada_jalur_wajar(fake_db):
    """
    Pemeriksaan yang BERHASIL tidak boleh membayar kueri tambahan.

    Nama itu hanya dipakai pada kalimat penolakan; membacanya setiap kali
    berarti setiap pemeriksaan menanggung satu perjalanan ke tabel pengguna
    demi kalimat yang hampir tidak pernah muncul.
    """
    db = _siapkan(fake_db, _dokumen())

    await _periksa()

    assert db.executed("fetch_val") == 0


@pytest.mark.asyncio
async def test_dokumen_yang_sudah_disetujui_ditolak(fake_db):
    """
    Memeriksa dokumen yang sudah disetujui menghasilkan `checkedAt` yang
    lebih baru daripada `approvedAt` — urutan yang tidak mungkin.
    """
    db = _siapkan(fake_db, _dokumen(isChecked=1, checkedBy=2, isApproved=1))

    hasil = await _periksa()

    assert hasil["code"] == ErrorCode.PO_ALREADY_APPROVED
    assert hasil["status"] == 409
    assert not _perintah_ubah(db)


@pytest.mark.asyncio
async def test_dokumen_tidak_ada_dijawab_404(fake_db):
    db = fake_db(MODUL, AUDIT)
    db.queue("fetch_one", None)

    hasil = await _periksa()

    assert hasil["status"] == 404
    assert not _perintah_ubah(db)


@pytest.mark.asyncio
async def test_jalur_wajar_tetap_lewat(fake_db):
    """
    Aturan yang menolak semua orang sama tidak bergunanya dengan aturan yang
    menerima semua orang — bedanya yang pertama menghentikan pekerjaan.
    """
    db = _siapkan(fake_db, _dokumen())

    hasil = await _periksa()

    assert "error" not in hasil
    assert _perintah_ubah(db)


# ---------------------------------------------------------------------
# Lapis 2: syaratnya ada DI DALAM perintah, bukan hanya di pembacaan.
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_syarat_keadaan_ikut_ke_dalam_where(fake_db):
    """
    Inilah yang memisahkan dua permintaan yang datang berbarengan.

    Keduanya membaca `isChecked = 0` dan keduanya lolos penjagaan di atas.
    Yang menyisakan satu pemenang hanya syarat pada perintahnya sendiri.

    Yang diperiksa SQL yang benar-benar terbentuk, bukan teks sumbernya:
    penjagaan yang ditulis tetapi tidak pernah sampai ke WHERE persis
    seperti tidak ada.
    """
    db = _siapkan(fake_db, _dokumen())

    await _periksa()

    perintah = _perintah_ubah(db)[0]
    where = perintah[perintah.index("WHERE") :]
    assert '"isChecked"' in where, (
        f"syarat keadaan tidak sampai ke WHERE: {where}"
    )
    assert '"isApproved"' in where


@pytest.mark.asyncio
async def test_kalah_balapan_dijawab_409_bukan_sukses(fake_db):
    """
    Nol baris terpengaruh berarti orang lain mendahului.

    Menjawabnya "tersimpan" membuat yang kalah mengira pemeriksaannya
    tercatat, padahal yang tercatat nama orang lain.
    """
    db = _siapkan(fake_db, _dokumen())
    db.queue("execute", 0)

    hasil = await _periksa()

    assert hasil["code"] == ErrorCode.PO_ALREADY_CHECKED
    assert hasil["status"] == 409


@pytest.mark.asyncio
async def test_versi_baris_ikut_dinaikkan(fake_db):
    """
    Formulir sunting yang terlanjur dibuka harus tahu barisnya bergerak.
    """
    db = _siapkan(fake_db, _dokumen())

    await _periksa()

    assert '"rowVersion"' in _perintah_ubah(db)[0]


# ---------------------------------------------------------------------
# Pencabutan TIDAK ikut dipersempit.
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pencabutan_tidak_dijaga_jumlah_baris(fake_db):
    """
    Mencabut menulis nilai yang mungkin SAMA dengan yang sudah ada, sehingga
    nol baris berubah tidak dapat dibedakan dari "didahului orang lain".

    Ikut menjaganya dengan cara yang sama berarti tombol "Cabut" pada
    dokumen yang memang belum diperiksa menjawab galat — galat pada tombol
    yang tidak melakukan apa-apa.
    """
    db = fake_db(MODUL, AUDIT)
    db.queue("fetch_one", _dokumen(isChecked=0), _dokumen())
    db.queue("execute", 0)

    hasil = await PurchaseOrderRepository.set_checked(
        9, False, ORANG_KEDUA, user_level=4
    )

    assert "error" not in hasil


# ---------------------------------------------------------------------
# Persetujuan: kelas yang sama, di pintu yang berbeda.
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persetujuan_kedua_ditolak(fake_db):
    """
    Tanpa ini, persetujuan kedua menimpa `approvedBy` dan `approvedAt` milik
    penyetuju pertama — dan dokumen tercetak atas nama orang yang tidak
    pernah menekan tombolnya.
    """
    db = fake_db(MODUL, AUDIT)
    db.queue("fetch_val", PEMBUAT)  # createdBy
    db.queue(
        "fetch_one",
        {"isChecked": 1, "checkedBy": PEMERIKSA_PERTAMA, "isApproved": 1},
    )

    hasil = await PurchaseOrderRepository.update_status(
        9, "approved", ORANG_KEDUA, user_level=4
    )

    assert hasil["code"] == ErrorCode.PO_ALREADY_APPROVED
    assert hasil["status"] == 409
    assert not _perintah_ubah(db)


@pytest.mark.asyncio
async def test_syarat_persetujuan_ikut_ke_dalam_where(fake_db):
    db = fake_db(MODUL, AUDIT)
    db.queue("fetch_val", PEMBUAT)
    db.queue(
        "fetch_one",
        {"isChecked": 1, "checkedBy": PEMERIKSA_PERTAMA, "isApproved": 0},
    )
    db.queue("fetch_one", {"id": 9, "status": "draft"})

    await PurchaseOrderRepository.update_status(
        9, "approved", ORANG_KEDUA, user_level=4
    )

    perintah = _perintah_ubah(db)[0]
    where = perintah[perintah.index("WHERE") :]
    assert '"isApproved"' in where, f"syarat tidak sampai ke WHERE: {where}"


@pytest.mark.asyncio
async def test_pembatalan_tidak_ikut_dipersempit(fake_db):
    """
    Menolak dan mengembalikan ke draf boleh dijalankan berulang.

    Dokumen yang sudah dibatalkan lalu dibatalkan lagi menulis nilai yang
    sama; menjaganya dengan jumlah baris membuat tombolnya menjawab galat.
    """
    db = fake_db(MODUL, AUDIT)
    db.queue("fetch_one", {"id": 9, "status": "rejected"})
    db.queue("execute", 0)

    hasil = await PurchaseOrderRepository.update_status(
        9, "rejected", ORANG_KEDUA, user_level=4
    )

    assert "error" not in hasil
