"""
Pengujian aturan persetujuan pembayaran keluar.

Aturannya: pembayaran tidak dapat disetujui oleh orang yang membuatnya,
kecuali oleh pemilik usaha (akses 5) — dan pengecualian itu ditandai pada
jejak aktivitas.

Diuji karena aturan ini mudah hilang tanpa disadari. Ia tidak terlihat di
layar mana pun; satu-satunya tempatnya adalah beberapa baris di controller,
dan menghapusnya tidak membuat apa pun gagal — sistem tetap berjalan, hanya
persetujuannya kehilangan guna.
"""

from types import SimpleNamespace

import pytest

# Diimpor di dalam fixture, bukan di puncak berkas.
#
# Rantai impornya menyentuh `models/balance_model.py`, yang memakai
# `autoload_with=engine` — pembacaan struktur tabel yang menyambung ke MySQL
# pada saat modul dimuat. Mengimpornya di sini akan menghentikan seluruh
# pengumpulan pengujian pada mesin tanpa basis data.
PaymentOutgoingController = None


def bayar(pid: int, created_by: int, *, approved=False, deleted=False):
    """
    Satu baris pembayaran secukupnya untuk diuji.

    Kolom dokumen sumber (purchase, reimbursement, dan seterusnya) diisi
    kosong: setelah status diperbarui, controller menelusuri dokumen asalnya
    untuk menyesuaikan statusnya, dan yang diuji di sini bukan bagian itu.
    """
    return SimpleNamespace(
        id=pid,
        createdBy=created_by,
        isApprove=approved,
        isDelete=deleted,
        purchaseID=None,
        reimbursementID=None,
        expenseID=None,
        loanID=None,
        salarySlipID=None,
        interpaymentID=None,
    )


@pytest.fixture
def repo(monkeypatch):
    """
    Ganti repository dengan tiruan.

    Yang diuji keputusannya, bukan penyimpanannya — sehingga tidak ada MySQL
    yang perlu dijalankan.
    """
    keadaan = {"payments": [], "dipanggil": False}

    async def _get(ids):
        return keadaan["payments"]

    async def _update(ids, status, user_id):
        keadaan["dipanggil"] = True
        return {"message": "Status updated successfully"}

    global PaymentOutgoingController
    from controllers import payment_outgoing_controller as modul

    PaymentOutgoingController = modul.PaymentOutgoingController

    monkeypatch.setattr(
        modul.PaymentOutgoingRepository, "get_payments_by_ids", staticmethod(_get)
    )
    monkeypatch.setattr(
        modul.PaymentOutgoingRepository, "update_bulk_status", staticmethod(_update)
    )
    return keadaan


@pytest.mark.asyncio
async def test_menyetujui_pembayaran_orang_lain_boleh(repo):
    repo["payments"] = [bayar(1, created_by=7)]

    hasil = await PaymentOutgoingController.update_bulk_payment_status(
        [1], "approve", userID=9, userLevel=4
    )

    assert "error" not in hasil
    assert repo["dipanggil"] is True


@pytest.mark.asyncio
async def test_menyetujui_buatan_sendiri_ditolak(repo):
    """Akses 4 tidak boleh menyetujui pembayaran yang dibuatnya sendiri."""
    repo["payments"] = [bayar(1, created_by=9)]

    hasil = await PaymentOutgoingController.update_bulk_payment_status(
        [1], "approve", userID=9, userLevel=4
    )

    assert hasil["status"] == 403
    assert "sendiri" in hasil["error"].lower()
    # Yang penting bukan hanya pesannya: penyimpanannya tidak boleh tersentuh.
    assert repo["dipanggil"] is False


@pytest.mark.asyncio
async def test_pemilik_usaha_boleh_menyetujui_buatan_sendiri(repo):
    """
    Pengecualian untuk akses 5.

    Pada perusahaan sekecil AKN, mewajibkan orang kedua untuk pembayaran yang
    dibuat pemilik di luar jam kerja tidak menambah pengendalian — yang
    terjadi justru pembayarannya diselesaikan di luar sistem.
    """
    repo["payments"] = [bayar(1, created_by=1)]

    hasil = await PaymentOutgoingController.update_bulk_payment_status(
        [1], "approve", userID=1, userLevel=5
    )

    assert "error" not in hasil
    assert repo["dipanggil"] is True


@pytest.mark.asyncio
async def test_menolak_buatan_sendiri_tetap_boleh(repo):
    """
    Larangan hanya berlaku pada persetujuan.

    Membatalkan pembayaran yang salah adalah membetulkan kekeliruan sendiri,
    bukan mengizinkan uang keluar.
    """
    repo["payments"] = [bayar(1, created_by=9)]

    hasil = await PaymentOutgoingController.update_bulk_payment_status(
        [1], "reject", userID=9, userLevel=4
    )

    assert "error" not in hasil


@pytest.mark.asyncio
async def test_pembayaran_yang_sudah_disetujui_ditolak(repo):
    repo["payments"] = [bayar(1, created_by=7, approved=True)]

    hasil = await PaymentOutgoingController.update_bulk_payment_status(
        [1], "approve", userID=9, userLevel=5
    )

    assert hasil["status"] == 400
    assert repo["dipanggil"] is False


@pytest.mark.asyncio
async def test_pembayaran_yang_sudah_dihapus_ditolak(repo):
    repo["payments"] = [bayar(1, created_by=7, deleted=True)]

    hasil = await PaymentOutgoingController.update_bulk_payment_status(
        [1], "approve", userID=9, userLevel=5
    )

    assert hasil["status"] == 400
    assert repo["dipanggil"] is False


@pytest.mark.asyncio
async def test_satu_baris_terlarang_membatalkan_seluruh_kumpulan(repo):
    """
    Persetujuan massal berhenti bila ada satu yang tidak boleh.

    Meloloskan sisanya diam-diam membuat penggunanya mengira semuanya
    disetujui, dan selisihnya baru terlihat saat dicocokkan.
    """
    repo["payments"] = [bayar(1, created_by=7), bayar(2, created_by=9)]

    hasil = await PaymentOutgoingController.update_bulk_payment_status(
        [1, 2], "approve", userID=9, userLevel=4
    )

    assert hasil["status"] == 403
    assert repo["dipanggil"] is False


@pytest.mark.asyncio
async def test_level_tidak_diketahui_diperlakukan_paling_ketat(repo):
    """Bila level tidak terkirim, jangan menganggapnya pemilik usaha."""
    repo["payments"] = [bayar(1, created_by=9)]

    hasil = await PaymentOutgoingController.update_bulk_payment_status(
        [1], "approve", userID=9
    )

    assert hasil["status"] == 403


# ---------------------------------------------------------------------------
# Level pengguna dibaca dari objek yang benar
# ---------------------------------------------------------------------------


class RecordPalsu:
    """
    Tiruan `Record` dari pustaka `databases`.

    Mendukung `record["kolom"]` tetapi TIDAK memiliki `.get()` — persis
    seperti objek yang dikembalikan `require()`. Kekeliruan memakai `.get()`
    pernah membuat persetujuan gagal dengan galat yang tidak menyebut
    sebabnya, dan pemilik usaha ikut tertahan padahal dikecualikan.
    """

    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]


def test_level_dibaca_tanpa_metode_get():
    """Cara membaca level harus bekerja pada objek Record, bukan dict saja."""
    user = RecordPalsu({"id": 1, "authenticationLevel": 5})

    assert not hasattr(user, "get")
    assert int(user["authenticationLevel"] or 1) == 5


def test_rute_persetujuan_tidak_memakai_get():
    """
    Menjaga cara pembacaannya di berkas rute.

    Diperiksa pada berkasnya karena kekeliruan ini tidak dapat ditangkap
    dengan memanggil controller — galatnya terjadi lebih dulu, di rutenya.
    """
    from pathlib import Path

    berkas = (
        Path(__file__).resolve().parents[1] / "routes" / "payment_outgoing_routes.py"
    )
    isi = berkas.read_text(encoding="utf-8")

    assert 'user.get("authenticationLevel")' not in isi
    assert 'user["authenticationLevel"]' in isi


def test_kedua_pintu_persetujuan_meneruskan_level():
    """
    Persetujuan satu per satu dan sekaligus adalah dua pintu berbeda.

    Keduanya harus meneruskan level; pintu yang tidak meneruskannya akan
    memakai nilai bawaan paling rendah, sehingga pemilik usaha ikut tertahan.
    """
    from pathlib import Path

    berkas = (
        Path(__file__).resolve().parents[1] / "routes" / "payment_outgoing_routes.py"
    )
    isi = berkas.read_text(encoding="utf-8")

    assert isi.count("userLevel") >= 4, "salah satu pintu tidak meneruskan level"


def test_penandaan_membaca_objek_lewat_atribut():
    """
    `get_payments_by_ids` mengembalikan objek PaymentOutgoing, bukan baris
    basis data — nilainya dibaca lewat atribut, bukan kunci.

    Memakai `p["id"]` pada objek itu melempar TypeError, dan karena letaknya
    di dalam blok penyimpanan, seluruh persetujuan gagal dengan galat yang
    tidak menyebut sebabnya.
    """

    class ObjekModel:
        def __init__(self, i, cb):
            self.id = i
            self.createdBy = cb

    data = [ObjekModel(10709, 1), ObjekModel(10710, 3)]

    # Objek model memang tidak mendukung [].
    with pytest.raises(TypeError):
        data[0]["id"]

    pembuat = {p.id: getattr(p, "createdBy", None) for p in data}
    assert pembuat == {10709: 1, 10710: 3}


def test_repository_tidak_membaca_objek_dengan_kunci():
    """Menjaga cara pembacaannya di berkas repository."""
    import re
    from pathlib import Path

    berkas = (
        Path(__file__).resolve().parents[1]
        / "repository"
        / "payment_outgoing_repository.py"
    )
    baris_kode = [
        b
        for b in berkas.read_text(encoding="utf-8").split("\n")
        if not b.lstrip().startswith("#")
    ]
    isi = "\n".join(baris_kode)

    assert not re.search(r'\bp\[\s*[\'"]id[\'"]\s*\]', isi)
