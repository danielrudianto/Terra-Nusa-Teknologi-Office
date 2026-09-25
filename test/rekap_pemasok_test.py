"""
Rekap purchase order per PEMASOK — sudut pandang kedua, jalur yang sama.

KENAPA SATU METHOD, BUKAN DUA

Rekap per proyek dan rekap per pemasok menjawab pertanyaan yang berbeda
("berapa yang sudah kita keluarkan di proyek ini" vs "sudah berapa banyak
kita pesan ke vendor ini"), tetapi DATANYA sama persis: dokumen yang sama,
baris yang sama, bentuk berkas yang sama. Yang berbeda satu baris `WHERE`.

Dua salinan kueri yang harus tetap sepakat adalah cara paling pasti membuat
kedua rekap menyebut angka berbeda untuk dokumen yang sama, begitu salah
satunya diperbaiki sendirian. Karena itu yang diuji di sini bukan hanya
penyaringnya, melainkan bahwa keduanya melewati kueri yang sama.

YANG DIJAGA PALING KERAS: TEPAT SATU

Tanpa keduanya, kueri ini mengembalikan SELURUH purchase order perusahaan —
berkas raksasa yang tidak diminta siapa pun, dan tidak ada galat apa pun yang
menyebutkannya. Dengan keduanya, judul berkasnya hanya dapat menyebut salah
satu, sehingga isinya tidak sesuai judulnya.
"""

import asyncio

import pytest

from repository.purchase_order_repository import PurchaseOrderRepository

MODUL = "repository.purchase_order_repository"


def _where(kueri: str) -> str:
    """
    Hanya klausa WHERE-nya.

    `po.supplierID` juga muncul pada JOIN ke tabel pemasok, dan
    `po.projectName` pada ORDER BY — memeriksa seluruh teks kueri membuat
    "tidak menyaring per pemasok" mustahil dinyatakan.
    """
    if "WHERE" not in kueri:
        return ""
    sisa = kueri.split("WHERE", 1)[1]
    for penutup in ("ORDER BY", "GROUP BY", "LIMIT"):
        if penutup in sisa:
            sisa = sisa.split(penutup, 1)[0]
    return sisa


def _jalankan(fake_db, **kwargs):
    db = fake_db(MODUL)
    # Dokumen kosong menghentikan langkah berikutnya; kueri pertama sudah
    # memuat seluruh penyaringnya.
    db.queue("fetch_all", [])
    hasil = asyncio.run(PurchaseOrderRepository.rekap(**kwargs))
    return str(db.last_query("fetch_all") or ""), db, hasil


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


class TestPenyaring:
    def test_pemasok_menyaring_supplierID(self, fake_db):
        kueri, db, _ = _jalankan(fake_db, supplier_id=17)

        assert "po.supplierID = :pemasok" in _where(kueri)
        assert "po.projectName" not in _where(kueri)
        assert db.last_values("fetch_all")["pemasok"] == 17

    def test_proyek_tetap_seperti_dulu(self, fake_db):
        kueri, db, _ = _jalankan(fake_db, project_name="R501")

        assert "po.projectName = :proyek" in _where(kueri)
        assert "po.supplierID" not in _where(kueri)
        assert db.last_values("fetch_all")["proyek"] == "R501"

    def test_dokumen_terhapus_dikecualikan_pada_KEDUANYA(self, fake_db):
        for arg in ({"project_name": "R501"}, {"supplier_id": 17}):
            kueri, _, _ = _jalankan(fake_db, **arg)
            assert "po.isDelete = 0" in _where(kueri), arg

    def test_rentang_berlaku_pada_pemasok_juga(self, fake_db):
        kueri, db, _ = _jalankan(
            fake_db, supplier_id=17, dari="2026-08-01", sampai="2026-08-31"
        )

        assert "po.date >= :dari" in _where(kueri)
        assert "po.date <= :sampai" in _where(kueri)
        nilai = db.last_values("fetch_all")
        assert nilai["dari"] == "2026-08-01"
        assert nilai["sampai"] == "2026-08-31"


class TestTepatSatu:
    def test_tanpa_keduanya_ditolak(self, fake_db):
        """
        Bukan "kembalikan semuanya": berkas berisi seluruh purchase order
        perusahaan tidak pernah diminta siapa pun, dan tidak ada judul yang
        dapat menyebutnya dengan benar.
        """
        kueri, _, hasil = _jalankan(fake_db)

        assert hasil.get("status") == 400
        assert _kode(hasil)
        # Dan tidak satu pun kueri dijalankan.
        assert kueri == ""

    def test_keduanya_sekaligus_ditolak(self, fake_db):
        kueri, _, hasil = _jalankan(fake_db, project_name="R501", supplier_id=17)

        assert hasil.get("status") == 400
        assert kueri == ""

    @pytest.mark.parametrize("kosong", ["", "   ", None])
    def test_proyek_kosong_bukan_berarti_disebut(self, fake_db, kosong):
        """
        `proyek=""` dari querystring tidak boleh terbaca sebagai "proyek
        disebut" — ia akan menghasilkan `projectName = ''`, yang cocok dengan
        nol dokumen dan terbaca sebagai "proyeknya memang belum punya apa-apa".
        """
        _, _, hasil = _jalankan(fake_db, project_name=kosong, supplier_id=17)
        assert hasil.get("status") != 400

    def test_proyek_kosong_TANPA_pemasok_tetap_ditolak(self, fake_db):
        _, _, hasil = _jalankan(fake_db, project_name="  ")
        assert hasil.get("status") == 400


class TestUrutan:
    def test_per_pemasok_diurut_proyek_lalu_nomor(self, fake_db):
        """
        Per pemasok, dokumennya datang dari banyak proyek. `number` saja
        mengacak proyeknya, dan yang membaca rekap vendor membacanya per
        proyek.
        """
        kueri, _, _ = _jalankan(fake_db, supplier_id=17)
        assert "ORDER BY po.projectName ASC, po.number ASC" in kueri

    def test_per_proyek_urutannya_tidak_berubah_artinya(self, fake_db):
        # Dalam satu proyek, `projectName` sama untuk semua baris, sehingga
        # urutannya tetap ditentukan `number` — persis seperti dulu.
        kueri, _, _ = _jalankan(fake_db, project_name="R501")
        assert "po.number ASC" in kueri


class TestBentukJawaban:
    def test_kosong_menjawab_bentuk_yang_sama(self, fake_db):
        """
        Layar membaca `purchaseOrders` dan `items`; jawaban kosong yang
        bentuknya berbeda membuatnya melempar alih-alih menampilkan "tidak
        ada".
        """
        _, _, hasil = _jalankan(fake_db, supplier_id=17)
        assert hasil == {"purchaseOrders": [], "items": []}

    def test_nama_pemasok_tetap_ikut(self, fake_db):
        # Rekap per pemasok pun mencetak nama pemasoknya di kepala berkas.
        kueri, _, _ = _jalankan(fake_db, supplier_id=17)
        assert "s.name AS supplierName" in kueri
