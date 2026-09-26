"""
Rekap certificate of payment — penyaring, susunan, dan penjagaannya.

KENAPA BENTUKNYA MENIRU REKAP PURCHASE ORDER

Yang memakai kedua rekap ini orang yang sama, pada hari yang sama, untuk
menjawab pertanyaan yang bersebelahan: "apa yang kita PESAN" dan "apa yang
sudah kita SERTIFIKASI". Dua bentuk penyaring yang berbeda untuk dua
pertanyaan yang berdampingan hanya melahirkan satu kesalahan baru — rentang
tanggal yang disangka sama padahal tidak. Karena itu nama parameter, sifat
pilihannya, dan syarat "sekurangnya salah satu" dijaga tetap sama di sini.

TIGA HAL YANG GAGAL DENGAN DIAM BILA SALAH

1. PEMASOK ADA DI SPK, BUKAN DI CoP. `certificate_of_payments` tidak punya
   kolom `supplierID` sama sekali. Menyaring `c.supplierID` bukan galat SQL
   yang terbaca — kolomnya memang tidak ada, dan yang muncul galat internal
   tanpa sebab. Yang benar `po.supplierID`.

2. NILAI TIDAK DIHITUNG ULANG. `grossAmount`, `deductionTotal`,
   `additionTotal`, dan `netAmount` sudah tersimpan sebagai kolom.
   Menjumlahkan ulang dari barisnya di kueri rekap berarti dua tempat yang
   harus tetap sepakat tentang satu angka — dan yang berselisih bukan galat,
   melainkan rekap yang menyebut angka berbeda dari layar CoP-nya sendiri.

3. NILAI KONTRAK TIDAK BOLEH N+1. `nilai_kontrak()` memakai tiga kueri per
   SPK. Dipanggil sekali per dokumen, rekap satu proyek berisi lima puluh
   SPK menjadi seratus lima puluh kueri — dan rekapnya melambat justru pada
   proyek yang paling perlu direkap. Uji di bawah menghitung kuerinya, bukan
   mempercayai bentuk kodenya.
"""

import asyncio

import pytest

from repository.certificate_of_payment_repository import (
    CertificateOfPaymentRepository,
)

MODUL = "repository.certificate_of_payment_repository"


def _where(kueri: str) -> str:
    """
    Hanya klausa WHERE-nya.

    `po.supplierID` juga muncul pada JOIN ke tabel pemasok, dan `s.name`
    pada ORDER BY — memeriksa seluruh teks kueri membuat "tidak menyaring
    per pemasok" mustahil dinyatakan.
    """
    if "WHERE" not in kueri:
        return ""
    # `rsplit`, bukan `split`: subkueri TAGIHAN punya WHERE sendiri dan ia
    # muncul LEBIH DULU. Mengambil yang pertama berarti memeriksa penyaring
    # tabel `purchases`, bukan penyaring rekapnya — dan seluruh pernyataan
    # di bawah menjadi tidak berarti tanpa satu pun gagal mencurigakan.
    sisa = kueri.rsplit("WHERE", 1)[1]
    for penutup in ("ORDER BY", "GROUP BY", "LIMIT"):
        if penutup in sisa:
            sisa = sisa.split(penutup, 1)[0]
    return sisa


def _kueri_pertama(fake_db, **kwargs):
    """Kueri dokumen — memuat seluruh penyaringnya. Hasil kosong menghentikan sisanya."""
    db = fake_db(MODUL)
    db.queue("fetch_all", [])
    hasil = asyncio.run(CertificateOfPaymentRepository.rekap(**kwargs))
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


# ---------------------------------------------------------------------------
# Sekurangnya satu sudut pandang
# ---------------------------------------------------------------------------


def test_tanpa_proyek_dan_tanpa_pemasok_ditolak(fake_db):
    db = fake_db(MODUL)
    hasil = asyncio.run(CertificateOfPaymentRepository.rekap())
    assert isinstance(hasil, dict)
    assert "VALIDATION" in _kode(hasil).upper()
    # Ditolak SEBELUM menyentuh basis data — bukan ditolak sesudah menarik
    # seluruh CoP perusahaan.
    assert db.executed("fetch_all") == 0


def test_proyek_kosong_atau_spasi_tidak_dianggap_terisi(fake_db):
    for nilai in ("", "   "):
        db = fake_db(MODUL)
        hasil = asyncio.run(CertificateOfPaymentRepository.rekap(project_name=nilai))
        assert "VALIDATION" in _kode(hasil).upper()
        assert db.executed("fetch_all") == 0


def test_pemasok_saja_cukup(fake_db):
    _, _, hasil = _kueri_pertama(fake_db, supplier_id=967)
    assert "VALIDATION" not in _kode(hasil).upper()


def test_proyek_saja_cukup(fake_db):
    _, _, hasil = _kueri_pertama(fake_db, project_name="R501")
    assert "VALIDATION" not in _kode(hasil).upper()


# ---------------------------------------------------------------------------
# Penyaringnya
# ---------------------------------------------------------------------------


def test_pemasok_disaring_lewat_SPK_bukan_kolom_di_CoP(fake_db):
    kueri, db, _ = _kueri_pertama(fake_db, supplier_id=967)
    w = _where(kueri)
    assert "po.supplierID" in w
    # Kolom ini TIDAK ADA di `certificate_of_payments`.
    assert "c.supplierID" not in w
    assert db.last_values("fetch_all")["pemasok"] == 967


def test_proyek_disaring_lewat_kolom_di_CoP(fake_db):
    kueri, db, _ = _kueri_pertama(fake_db, project_name="R501")
    assert "c.projectName" in _where(kueri)
    assert db.last_values("fetch_all")["proyek"] == "R501"


def test_keduanya_sekaligus_MENYEMPITKAN(fake_db):
    kueri, db, _ = _kueri_pertama(fake_db, project_name="R501", supplier_id=967)
    w = _where(kueri)
    assert "c.projectName" in w and "po.supplierID" in w
    nilai = db.last_values("fetch_all")
    assert nilai["proyek"] == "R501" and nilai["pemasok"] == 967


def test_rentang_tanggal_INKLUSIF_di_kedua_ujungnya(fake_db):
    kueri, db, _ = _kueri_pertama(
        fake_db, project_name="R501", dari="2026-09-01", sampai="2026-09-30"
    )
    w = _where(kueri)
    # Batas atas yang eksklusif menghilangkan dokumen hari terakhir tanpa
    # ada yang menyadarinya — jumlahnya tetap masuk akal.
    assert "c.date >= :dari" in w
    assert "c.date <= :sampai" in w
    nilai = db.last_values("fetch_all")
    assert nilai["dari"] == "2026-09-01" and nilai["sampai"] == "2026-09-30"


def test_tanggal_bersifat_pilihan(fake_db):
    kueri, _, _ = _kueri_pertama(fake_db, project_name="R501")
    w = _where(kueri)
    assert ":dari" not in w and ":sampai" not in w


def test_yang_terhapus_dikecualikan(fake_db):
    kueri, _, _ = _kueri_pertama(fake_db, project_name="R501")
    assert "c.isDelete = 0" in _where(kueri)


# ---------------------------------------------------------------------------
# Susunan & isinya
# ---------------------------------------------------------------------------


def test_disusun_pemasok_lalu_SPK_lalu_nomor(fake_db):
    kueri, _, _ = _kueri_pertama(fake_db, project_name="R501")
    urut = kueri.split("ORDER BY", 1)[1]
    # Susunan berkasnya ditentukan DI SINI, bukan di layar: dua unduhan atas
    # data yang sama tidak boleh berbeda susunan.
    assert urut.index("s.name") < urut.index("po.name") < urut.index("c.number")


def test_nilai_dibaca_dari_kolomnya_bukan_dihitung_ulang(fake_db):
    kueri, _, _ = _kueri_pertama(fake_db, project_name="R501")
    for kolom in ("grossAmount", "deductionTotal", "additionTotal", "netAmount"):
        assert f"c.{kolom}" in kueri
    # Penjumlahan ulang dari baris CoP akan melahirkan angka kedua yang
    # harus tetap sepakat dengan yang tersimpan.
    assert "SUM(ci.quantity" not in kueri.replace(" ", "")
    assert "SUM(ci.amount" not in kueri.replace(" ", "")


def test_tahap_dokumen_ikut_supaya_yang_belum_sah_dapat_ditandai(fake_db):
    kueri, _, _ = _kueri_pertama(fake_db, project_name="R501")
    for kolom in ("isBapApproved", "isCopCreated", "isApproved"):
        assert kolom in kueri


def test_keadaan_penagihan_ikut(fake_db):
    kueri, _, _ = _kueri_pertama(fake_db, project_name="R501")
    # "Sudah ditagihkan belum" adalah pertanyaan berikutnya sesudah "sudah
    # disertifikasi berapa"; rekap yang tidak menjawabnya memaksa orang
    # membuka daftar Pembelian satu per satu.
    assert "invoiceName" in kueri and "purchases" in kueri


def test_kosong_mengembalikan_daftar_kosong_bukan_galat(fake_db):
    _, _, hasil = _kueri_pertama(fake_db, project_name="R501")
    assert hasil == {"certificateOfPayments": [], "purchaseOrders": []}


# ---------------------------------------------------------------------------
# Nilai kontrak per SPK — jumlah kueri TIDAK boleh tumbuh
# ---------------------------------------------------------------------------


def _dokumen(cop_id: int, po_id: int, jenis: str = "B"):
    return {
        "id": cop_id,
        "name": f"00{cop_id}-967-R501-2026",
        "number": cop_id,
        "date": "2026-09-10",
        "periodStart": None,
        "periodEnd": None,
        "projectName": "R501",
        "note": None,
        "grossAmount": 1000,
        "deductionTotal": 0,
        "additionTotal": 0,
        "netAmount": 1000,
        "isBapApproved": 1,
        "isCopCreated": 1,
        "isApproved": 1,
        "purchaseOrderID": po_id,
        "purchaseOrderName": f"0{po_id}-SPK-R501-{jenis}",
        "purchaseType": jenis,
        "supplierID": 967,
        "supplierName": "Pemasok",
        "supplierPrefix": "CV",
        "tagihanNomor": None,
        "tagihanLunas": None,
    }


def _jalankan_penuh(fake_db, dokumen):
    db = fake_db(MODUL)
    po_ids = sorted({d["purchaseOrderID"] for d in dokumen})
    db.queue("fetch_all", dokumen)                                  # 1. dokumen
    db.queue("fetch_all", [{"id": p, "akar": p} for p in po_ids])   # 2. akar
    db.queue("fetch_all", [{"id": p, "akar": p} for p in po_ids])   # 3. anggota
    db.queue("fetch_all", [{"po": p, "nilai": 5_000_000} for p in po_ids])  # 4. jumlah
    db.queue("fetch_all", [])                                       # 5. peta borongan
    hasil = asyncio.run(
        CertificateOfPaymentRepository.rekap(project_name="R501")
    )
    return hasil, db


def test_jumlah_kueri_TIDAK_tumbuh_mengikuti_banyaknya_SPK(fake_db):
    _, db_satu = _jalankan_penuh(fake_db, [_dokumen(1, 101)])
    _, db_banyak = _jalankan_penuh(
        fake_db, [_dokumen(i, 100 + i) for i in range(1, 13)]
    )
    # Dua belas SPK harus memakai kueri sebanyak satu SPK. Bila `nilai_kontrak()`
    # dipanggil per dokumen, angka kanan melonjak tiga kali lipat per SPK.
    assert db_banyak.executed("fetch_all") == db_satu.executed("fetch_all")


def test_nilai_kontrak_terpasang_pada_tiap_SPK(fake_db):
    hasil, _ = _jalankan_penuh(fake_db, [_dokumen(1, 101), _dokumen(2, 102)])
    spk = {s["id"]: s for s in hasil["purchaseOrders"]}
    assert set(spk) == {101, 102}
    assert int(spk[101]["nilaiKontrak"]) == 5_000_000


def test_satu_baris_SPK_per_dokumen_walau_CoP_nya_banyak(fake_db):
    hasil, _ = _jalankan_penuh(
        fake_db, [_dokumen(1, 101), _dokumen(2, 101), _dokumen(3, 101)]
    )
    assert len(hasil["purchaseOrders"]) == 1
    assert len(hasil["certificateOfPayments"]) == 3


def test_SPK_D_ditandai_TANPA_PAGU_bukan_diberi_sisa_nol(fake_db):
    hasil, _ = _jalankan_penuh(fake_db, [_dokumen(1, 101, jenis="D")])
    # Jenis D tidak punya plafon: volumenya ditentukan di berita acara.
    # "Sisa pagu" di sana menyebut batas yang tidak ada — dan angka yang
    # tercetak selalu dibaca sebagai kesepakatan.
    assert hasil["purchaseOrders"][0]["tanpaPagu"] is True


def test_SPK_selain_D_tetap_berpagu(fake_db):
    hasil, _ = _jalankan_penuh(fake_db, [_dokumen(1, 101, jenis="B")])
    assert hasil["purchaseOrders"][0]["tanpaPagu"] is False
