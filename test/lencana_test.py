"""
Lencana "menunggu SAYA" di menu samping.

Hitungan global tidak pernah nol pada perusahaan yang jalan, dan dalam dua
minggu setiap orang berhenti melihat titik merahnya — kelas kegagalan yang
sama seperti pemeriksa yang selalu merah. Lencana yang BISA nol adalah
lencana yang dilihat orang.

Karena itu yang dijaga di sini bukan "angkanya keluar", melainkan tiga hal
yang membuat angkanya berarti:

  * wewenangnya dihormati — yang tidak berhak menyetujui tidak melihat
    hitungan approval, dan hitungan itu tidak membocorkan keberadaan dokumen
    yang tidak boleh ia lihat;
  * dokumen SENDIRI dikecualikan, sama seperti tombolnya — kalau tidak,
    lencananya menampilkan angka yang tidak dapat diturunkan pemiliknya;
  * gagal menghitung dikembalikan sebagai `None`, BUKAN nol.
"""

from unittest.mock import patch

import pytest

from repository.lencana_repository import LencanaRepository


class _Tangkap:
    """Perekam kueri; tiap pemanggilan mengembalikan satu."""

    def __init__(self):
        self.kueri = []

    async def __call__(self, sql, nilai):
        self.kueri.append((" ".join(sql.split()), dict(nilai or {})))
        return 1


def _izin(jawab=True):
    async def _f(user, modul, aksi):
        return jawab
    return _f


# ----------------------------------------------------------------------
# Wewenang
# ----------------------------------------------------------------------


async def test_yang_tak_boleh_menyetujui_tidak_melihat_hitungannya():
    """
    Hitungan approval hanya untuk yang memang berwenang.

    Bukan sekadar kerapian: angka BUKAN isi, tetapi angka tetap keterangan.
    "Ada 7 dokumen menunggu persetujuan" pada layar orang yang tidak berhak
    menyetujui sudah menyatakan lebih daripada yang seharusnya — dan ia tidak
    dapat berbuat apa pun dengan angka itu selain bertanya-tanya.
    """
    t = _Tangkap()
    with patch("repository.lencana_repository._hitung", t), \
         patch("repository.lencana_repository.is_allowed", _izin(False)):
        n = await LencanaRepository.purchase_order({"id": 5}, 1, set())

    assert n == 0
    assert t.kueri == [], "level 1 tidak boleh memicu kueri apa pun"


async def test_reimbursement_nol_bila_tak_berwenang():
    t = _Tangkap()
    with patch("repository.lencana_repository._hitung", t), \
         patch("repository.lencana_repository.is_allowed", _izin(False)):
        assert await LencanaRepository.reimbursement({"id": 5}, 3) == 0
    assert t.kueri == []


# ----------------------------------------------------------------------
# Dokumen sendiri
# ----------------------------------------------------------------------


async def test_dokumen_buatan_sendiri_dikecualikan():
    """
    Lencana harus dapat DITURUNKAN oleh yang melihatnya.

    Tanpa pengecualian ini, yang mencatat sepuluh SPK melihat angka sepuluh
    yang tidak dapat ia kerjakan sendiri — aturan pembuat ≠ penyetuju akan
    menolaknya. Lencananya berubah menjadi penghitung pekerjaan orang lain,
    dan itu persis lencana yang tidak pernah nol.
    """
    t = _Tangkap()
    with patch("repository.lencana_repository._hitung", t), \
         patch("repository.lencana_repository.is_allowed", _izin(True)):
        await LencanaRepository.purchase_order({"id": 42}, 4, {"procurement"})

    for sql, nilai in t.kueri:
        assert "createdBy <> :uid" in sql, f"tidak mengecualikan pembuatnya: {sql}"
        assert nilai["uid"] == 42


async def test_dua_tahap_punya_aturan_diri_sendiri_yang_BERBEDA():
    """
    Memeriksa dan menyetujui tidak sama soal dokumen sendiri.

    `boleh_menyetujui_sendiri` longgar pada level 5: pada perusahaan sebesar
    ini pemilik kerap satu-satunya yang hadir untuk menyetujui, dan melarangnya
    berarti dokumen tertahan tanpa ada orang lain yang berwenang.

    `boleh_memeriksa_sendiri` TIDAK — ia mengembalikan False untuk SIAPA PUN,
    termasuk pemilik. Pemeriksaan justru ada untuk menghadirkan mata kedua;
    membiarkan pembuatnya memeriksa sendiri membuat tahap itu hanya menambah
    satu klik tanpa menambah apa pun.

    Uji ini ada karena saya sendiri sempat menyamakan keduanya saat
    menulisnya. Lencana yang menghitung dokumen yang tombolnya akan ditolak
    server adalah lencana yang mengajari pembacanya berhenti percaya.
    """
    t = _Tangkap()
    with patch("repository.lencana_repository._hitung", t), \
         patch("repository.lencana_repository.is_allowed", _izin(True)):
        await LencanaRepository.purchase_order({"id": 1}, 5, set())

    periksa = [q for q in t.kueri if "isChecked = 0" in q[0]]
    setujui = [q for q in t.kueri if "isChecked = 1" in q[0]]
    assert periksa and setujui

    # Memeriksa: pembuatnya tetap dikecualikan, walau ia pemilik.
    assert "createdBy <> :uid" in periksa[0][0]
    # Menyetujui: pemilik boleh atas dokumennya sendiri.
    assert "createdBy <>" not in setujui[0][0]


async def test_pemeriksa_tidak_menghitung_yang_diperiksanya_sendiri():
    """
    Yang MEMERIKSA sebuah SPK tidak boleh pula menyetujuinya.

    Tanpa saringan ini lencananya menghitung dokumen yang tombol setujuinya
    justru ditolak server saat ditekan — dan yang membacanya menyimpulkan
    lencananya rusak, lalu berhenti mempercayai seluruhnya.
    """
    t = _Tangkap()
    with patch("repository.lencana_repository._hitung", t), \
         patch("repository.lencana_repository.is_allowed", _izin(True)):
        await LencanaRepository.purchase_order({"id": 7}, 4, {"procurement"})

    approve = [q for q in t.kueri if "isChecked = 1" in q[0]]
    assert approve, "kueri tahap persetujuan tidak ada"
    assert "checkedBy" in approve[0][0]


# ----------------------------------------------------------------------
# Gagal menghitung
# ----------------------------------------------------------------------


async def test_gagal_menghitung_mengembalikan_none_bukan_nol():
    """
    Nol berarti "tidak ada yang menunggu Anda". `None` berarti "tidak tahu".

    Menyamakannya adalah berbohong ke arah yang paling merugikan: yang
    membacanya berhenti memeriksa justru karena hitungannya gagal.
    """
    async def meledak(*a, **k):
        raise RuntimeError("kolomnya hilang")

    with patch.object(LencanaRepository, "purchase_order", meledak), \
         patch.object(LencanaRepository, "reimbursement", meledak), \
         patch.object(LencanaRepository, "certificate_of_payment", meledak), \
         patch.object(LencanaRepository, "tender", meledak), \
         patch.object(LencanaRepository, "pembayaran", meledak):
        hasil = await LencanaRepository.semua({"id": 1}, 5, set())

    # Daftar kunci sengaja ditulis lengkap, bukan dicocokkan sebagian.
    #
    # Modul yang ditambahkan tanpa memperbarui uji ini akan lolos diam-diam —
    # dan kalau modul itu melempar, layar menerima jawaban yang kekurangan
    # satu kolom tanpa ada yang menandainya. Uji ini memang harus ikut
    # berubah setiap ada modul baru; itu fiturnya, bukan bebannya.
    assert set(hasil) == {
        "purchase_order",
        "reimbursement",
        "certificate_of_payment",
        "tender",
        "payment_plan",
    }
    for kunci, nilai in hasil.items():
        assert nilai is None, f"{kunci} dikembalikan {nilai!r}, seharusnya None"


async def test_satu_modul_gagal_tidak_menjatuhkan_yang_lain():
    """
    Menu samping tampil di SETIAP halaman.

    Satu hitungan yang bermasalah tidak boleh membuat seluruh aplikasi tidak
    dapat dibuka — dan itulah yang terjadi bila jawabannya dibiarkan gagal
    seluruhnya.
    """
    async def meledak(*a, **k):
        raise RuntimeError("tabelnya belum ada")

    async def nol(*a, **k):
        return 0

    with patch.object(LencanaRepository, "purchase_order", meledak), \
         patch.object(LencanaRepository, "reimbursement", nol), \
         patch.object(LencanaRepository, "certificate_of_payment", nol), \
         patch.object(LencanaRepository, "tender", nol), \
         patch.object(LencanaRepository, "pembayaran", nol):
        hasil = await LencanaRepository.semua({"id": 1}, 5, set())

    assert hasil["purchase_order"] is None
    assert hasil["reimbursement"] == 0
    assert hasil["certificate_of_payment"] == 0
    assert hasil["payment_plan"] == 0


# ----------------------------------------------------------------------
# Pembayaran — jenis angka yang BERBEDA
# ----------------------------------------------------------------------


async def test_pembayaran_menghitung_yang_sudah_lewat_juga():
    """
    Yang jatuh tempo KEMARIN justru yang paling perlu terlihat.

    Menyaringnya menjadi "hari ini saja" membuat rencana yang terlewat hilang
    dari pandangan tepat pada hari ia menjadi terlambat.
    """
    t = _Tangkap()
    with patch("repository.lencana_repository._hitung", t), \
         patch("repository.lencana_repository.is_allowed", _izin(True)):
        await LencanaRepository.pembayaran({"id": 1})

    sql = t.kueri[0][0]
    assert "date <= :hari_ini" in sql, "hanya menghitung hari ini, bukan yang lewat"
    assert "planType = 'keluar'" in sql
    assert "status = 'rencana'" in sql


# ----------------------------------------------------------------------
# `current_user` adalah Record, bukan dict
# ----------------------------------------------------------------------


class _Record(dict):
    """
    `databases.Record` secukupnya: boleh diindeks, TIDAK punya `.get()`.

    Bentuk inilah yang sebenarnya diterima controller. Menguji dengan dict
    biasa membuat seluruh berkas ini hijau sementara rutenya melempar 500 di
    produksi — dan galatnya sampai ke peramban sebagai keluhan CORS, bukan
    sebagai 500, sehingga menunjuk ke arah yang sama sekali salah.
    """

    get = None  # type: ignore[assignment]


async def test_controller_menerima_record_bukan_dict(monkeypatch):
    """
    Controller tidak boleh memanggil `.get()` pada `current_user`.

    Sudah tercatat di CLAUDE.md sebagai gotcha; uji ini yang menegakkannya.
    """
    from controllers.lencana_controller import LencanaController

    async def dept_palsu(uid):
        return set()

    async def semua_palsu(user, level, departemen):
        return {"purchase_order": level}

    monkeypatch.setattr(
        "controllers.lencana_controller._departments", dept_palsu
    )
    monkeypatch.setattr(LencanaRepository, "semua", semua_palsu)

    hasil = await LencanaController.semua(
        _Record({"id": 3, "authenticationLevel": 4})
    )
    assert hasil == {"purchase_order": 4}
