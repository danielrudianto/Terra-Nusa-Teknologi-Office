"""
POSISI KEUANGAN: kas yang dapat dipakai, likuiditas 30 hari, akurasi rencana.

Tiga kekeliruan yang dijaga di sini, dan ketiganya tidak menghasilkan galat
apa pun — hanya angka yang salah, pada layar yang dibuka justru untuk
mengambil keputusan.

1. KAS yang memuat rekening dikecualikan. Deposit jaminan adalah uang yang
   ada tetapi tidak dapat dibelanjakan. Ikut dijumlah, ia membesarkan
   pembilang quick ratio DAN suku pertama modal kerja bersih — jadi kedua
   ukuran kesehatan keuangan tampak lebih baik daripada keadaannya, dengan
   selisih persis sebesar jaminan yang tidak boleh disentuh.

2. LIKUIDITAS yang menjumlahkan rencana kas dengan utang usaha. Sebuah
   rencana keluar kerap dibuat untuk pembelian yang juga tercatat sebagai
   utang, dan tidak ada kolom apa pun yang menghubungkan keduanya — jadi
   tumpangnya tidak dapat dikenali, apalagi dikurangkan.

3. AKURASI yang dijadikan satu persentase. `aktual` memuat seluruh kas yang
   bergerak, termasuk yang tidak pernah direncanakan; `aktual / rencana`
   karena itu bukan akurasi.
"""

from datetime import date

import pytest

from controllers.finance_status_controller import FinanceStatusController as FS
from repository.finance_status_repository import FinanceStatusRepository as R


# --------------------------------------------------------------------------
# Batas bulan
# --------------------------------------------------------------------------


def test_batas_bulan_mundur_melewati_pergantian_tahun():
    """
    Mundur 5 bulan dari Januari harus sampai ke Agustus TAHUN SEBELUMNYA.

    Pengurangan bulan yang lupa meminjam dari tahun menghasilkan bulan nol
    atau minus — dan `date(2026, 0, 1)` melempar, sehingga yang terjadi bukan
    angka salah melainkan halaman yang mati, tetapi HANYA pada bulan-bulan
    awal tahun. Diuji lewat tanggal tetap, bukan hari ini.
    """
    awal, akhir = _batas(date(2026, 1, 15), mundur=5)
    assert awal == date(2025, 8, 1)
    assert akhir == date(2026, 2, 1)


def test_batas_atas_desember_pindah_ke_tahun_berikutnya():
    """Desember: batas atasnya 1 Januari tahun depan, bukan bulan ke-13."""
    awal, akhir = _batas(date(2026, 12, 3), mundur=0)
    assert awal == date(2026, 12, 1)
    assert akhir == date(2027, 1, 1)


def test_batas_atas_eksklusif_mencakup_hari_terakhir_bulan_ini():
    """
    Batas atas EKSKLUSIF, jadi 30 September tetap ikut terhitung.

    Kalau batasnya inklusif pada tanggal 1, transaksi hari terakhir bulan
    berjalan hilang dari grafik setiap bulan — dan bulan berjalan memang
    selalu yang paling diperhatikan.
    """
    _, akhir = _batas(date(2026, 9, 18), mundur=0)
    assert akhir == date(2026, 10, 1)


def _batas(hari_ini: date, mundur: int):
    """Panggil `_batas_bulan` dengan "hari ini" yang ditentukan."""
    import repository.finance_status_repository as modul

    asli = modul.d

    class TanggalPalsu(date):
        @classmethod
        def today(cls):
            return hari_ini

    modul.d = TanggalPalsu
    try:
        return R._batas_bulan(mundur)
    finally:
        modul.d = asli


# --------------------------------------------------------------------------
# Posisi keuangan
# --------------------------------------------------------------------------


@pytest.fixture
def repo(monkeypatch):
    """Tiru keempat sumbernya; tiap uji mengubah `keadaan`."""
    keadaan = {
        "kas": {"total": 100.0, "dikecualikan": 0.0, "jumlahDikecualikan": 0},
        "piutang": {
            "total": 60.0,
            "umur": {"0-30": 40.0, "31-60": 20.0, "61-90": 0.0, "90+": 0.0},
            "jumlahDokumen": 2,
        },
        "utang": {
            "total": 50.0,
            "tempo": {"lewat": 10.0, "0-30": 15.0, "31-60": 25.0, "60+": 0.0},
            "jumlahDokumen": 3,
        },
        "pinjaman": {"total": 500.0, "jumlahPinjaman": 1},
    }

    async def _kas():
        return keadaan["kas"]

    async def _piutang():
        return keadaan["piutang"]

    async def _utang():
        return keadaan["utang"]

    async def _pinjaman():
        return keadaan["pinjaman"]

    monkeypatch.setattr(R, "total_kas", staticmethod(_kas))
    monkeypatch.setattr(R, "piutang", staticmethod(_piutang))
    monkeypatch.setattr(R, "utang_usaha", staticmethod(_utang))
    monkeypatch.setattr(R, "pinjaman", staticmethod(_pinjaman))
    return keadaan


class TestKasDapatDipakai:

    @pytest.mark.asyncio
    async def test_rekening_dikecualikan_tidak_masuk_quick_ratio(self, repo):
        """
        Jaminan Rp 900 di samping kas Rp 100 TIDAK boleh menaikkan rasionya.

        Dengan utang 50: rasio yang benar (100+60)/50 = 3,2. Bila jaminannya
        ikut, ia menjadi (1000+60)/50 = 21,2 — perusahaan yang sama, tampak
        tujuh kali lebih likuid.
        """
        repo["kas"] = {
            "total": 100.0,
            "dikecualikan": 900.0,
            "jumlahDikecualikan": 1,
        }
        hasil = await FS.get_status()
        assert hasil["quickRatio"] == pytest.approx(3.2)
        assert hasil["modalKerjaBersih"] == pytest.approx(110.0)

    @pytest.mark.asyncio
    async def test_yang_dikecualikan_tetap_dilaporkan(self, repo):
        """
        Uangnya tetap ada, jadi ia tetap dicetak — terpisah.

        Angka yang dihilangkan sama sekali dari laporan adalah angka yang
        tidak pernah dicocokkan lagi dengan apa pun.
        """
        repo["kas"] = {
            "total": 100.0,
            "dikecualikan": 900.0,
            "jumlahDikecualikan": 1,
        }
        hasil = await FS.get_status()
        assert hasil["kasDikecualikan"] == 900.0
        assert hasil["catatan"]["kasTanpaRekeningDikecualikan"] is True

    @pytest.mark.asyncio
    async def test_tanpa_rekening_dikecualikan_catatannya_padam(self, repo):
        """Keterangan yang selalu menyala berhenti dibaca orang."""
        hasil = await FS.get_status()
        assert hasil["catatan"]["kasTanpaRekeningDikecualikan"] is False


class TestLikuiditas30Hari:

    @pytest.mark.asyncio
    async def test_kewajiban_30_hari_memuat_yang_sudah_lewat(self, repo):
        """
        Yang tenggatnya SUDAH lewat lebih mendesak daripada yang jatuh besok.

        Mengeluarkannya membuat kewajiban paling nyata justru yang paling
        tidak terlihat.
        """
        hasil = await FS.get_status()
        lik = hasil["likuiditas30"]
        assert lik["kewajibanLewat"] == 10.0
        assert lik["kewajiban30"] == 25.0
        assert lik["setelahKewajiban"] == 75.0

    @pytest.mark.asyncio
    async def test_kewajiban_yang_jauh_tidak_ikut(self, repo):
        """Ember 31-60 dan 60+ bukan urusan tiga puluh hari ke depan."""
        repo["utang"]["tempo"]["31-60"] = 9999.0
        hasil = await FS.get_status()
        assert hasil["likuiditas30"]["kewajiban30"] == 25.0

    @pytest.mark.asyncio
    async def test_piutang_TIDAK_ditambahkan_ke_kas(self, repo):
        """
        `sales_invoices` tidak menyimpan jatuh tempo.

        Jadi tidak ada dasar apa pun untuk mengatakan sebuah faktur akan
        tertagih dalam 30 hari. Menambahkannya menghasilkan angka likuiditas
        yang lebih besar daripada uang yang benar-benar akan ada — dan itulah
        angka yang dipakai memutuskan pembayaran.
        """
        repo["piutang"]["umur"]["0-30"] = 1_000_000.0
        hasil = await FS.get_status()
        lik = hasil["likuiditas30"]
        assert lik["setelahKewajiban"] == 75.0
        # Tetap DISEBUT, sebagai keterangan di sebelahnya.
        assert lik["piutangTermuda"] == 1_000_000.0
        assert hasil["catatan"]["piutangTanpaJatuhTempo"] is True

    @pytest.mark.asyncio
    async def test_rencana_kas_tidak_ikut_dijumlahkan(self, repo):
        """
        Rencana kas dan utang usaha DAPAT menunjuk pembelian yang sama.

        Tidak ada kolom yang menghubungkannya, jadi tumpangnya tidak dapat
        dikenali. Menjumlahkan keduanya berarti mengurangi satu pembayaran
        dua kali — dan selisihnya tidak dapat dijelaskan kepada siapa pun
        yang bertanya.
        """
        hasil = await FS.get_status()
        assert hasil["catatan"]["rencanaKasTidakDijumlahkan"] is True
        assert "rencana" not in hasil["likuiditas30"]

    @pytest.mark.asyncio
    async def test_kas_kurang_dari_kewajibannya_boleh_minus(self, repo):
        """
        Angka minus adalah jawabannya, bukan kekeliruan yang perlu dijepit.

        Membatasinya pada nol menyembunyikan justru keadaan yang layar ini
        ada untuk memperlihatkannya.
        """
        repo["kas"] = {"total": 5.0, "dikecualikan": 0.0, "jumlahDikecualikan": 0}
        hasil = await FS.get_status()
        assert hasil["likuiditas30"]["setelahKewajiban"] == -20.0


class TestBatasAkurasi:

    @pytest.mark.asyncio
    async def test_mundur_dijepit_pada_batas(self, monkeypatch):
        """
        `?mundur=999` akan memindai seluruh riwayat.

        Tidak ada galat yang muncul; layarnya hanya diam makin lama setiap
        tahun berjalan.
        """
        ditangkap = {}

        async def _palsu(mundur):
            ditangkap["mundur"] = mundur
            return {"bulanan": []}

        monkeypatch.setattr(R, "akurasi_rencana", staticmethod(_palsu))
        await FS.akurasi_rencana(999)
        assert ditangkap["mundur"] == FS.MAKS_MUNDUR

    @pytest.mark.asyncio
    async def test_mundur_negatif_dijepit_pada_nol(self, monkeypatch):
        ditangkap = {}

        async def _palsu(mundur):
            ditangkap["mundur"] = mundur
            return {"bulanan": []}

        monkeypatch.setattr(R, "akurasi_rencana", staticmethod(_palsu))
        await FS.akurasi_rencana(-3)
        assert ditangkap["mundur"] == 0
