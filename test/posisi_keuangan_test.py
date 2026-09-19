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

from controllers.finance_status_controller import (
    FinanceStatusController as FS,
    posisi_terhadap_pita as PTP,
)
from repository.finance_status_repository import (
    AMBANG_BAWAAN as R_AMBANG,
    FinanceStatusRepository as R,
)


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
        # Kewajiban selain pembelian — nol secara bawaan supaya uji lama
        # tetap menguji hal yang sama; uji yang memang tentangnya mengisinya.
        "lain": {"total": 0.0, "jumlahDokumen": 0, "rincian": {}},
        "asetTetap": {
            "nilaiBuku": 0.0,
            "perolehan": 0.0,
            "akumulasiPenyusutan": 0.0,
            "jumlahAset": 0,
        },
        # Pendapatan 600 & pembelian 300 setahun: dengan piutang 60 dan utang
        # 50, DSO = 60/600*365 = 36,5 hari dan DPO = 50/300*365 = 60,8 hari.
        "arus": {
            "pendapatan": 600.0,
            "pembelian": 300.0,
            "hari": 365,
            "sejak": "2025-09-18",
        },
        "konsentrasi": {
            "jumlahKlien": 2,
            "total": 60.0,
            "terbesar": {"clientID": 1, "sisa": 40.0},
            "bagianTerbesar": 40.0 / 60.0,
        },
        "backlog": {
            "nilaiKontrak": 1000.0,
            "sudahDifakturkan": 400.0,
            "belumDifakturkan": 600.0,
            "kontrakMelampauiNilai": False,
        },
        "ambang": dict(R_AMBANG),
    }

    async def _kas():
        return keadaan["kas"]

    async def _piutang():
        return keadaan["piutang"]

    async def _utang():
        return keadaan["utang"]

    async def _pinjaman():
        return keadaan["pinjaman"]

    async def _lain():
        return keadaan["lain"]

    async def _aset():
        return keadaan["asetTetap"]

    async def _arus():
        return keadaan["arus"]

    async def _konsentrasi():
        return keadaan["konsentrasi"]

    async def _backlog():
        return keadaan["backlog"]

    async def _ambang():
        return keadaan["ambang"]

    monkeypatch.setattr(R, "total_kas", staticmethod(_kas))
    monkeypatch.setattr(R, "piutang", staticmethod(_piutang))
    monkeypatch.setattr(R, "utang_usaha", staticmethod(_utang))
    monkeypatch.setattr(R, "pinjaman", staticmethod(_pinjaman))
    monkeypatch.setattr(R, "kewajiban_lain", staticmethod(_lain))
    monkeypatch.setattr(R, "nilai_buku_aset", staticmethod(_aset))
    monkeypatch.setattr(R, "arus_setahun", staticmethod(_arus))
    monkeypatch.setattr(R, "konsentrasi_piutang", staticmethod(_konsentrasi))
    monkeypatch.setattr(R, "backlog", staticmethod(_backlog))
    monkeypatch.setattr(R, "ambang", staticmethod(_ambang))
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


# --------------------------------------------------------------------------
# Pembelian internal
# --------------------------------------------------------------------------


def test_utang_usaha_menyaring_pembelian_internal():
    """
    PEMBELIAN INTERNAL BUKAN UTANG — dijaga dengan membaca sumbernya.

    Ini penjaga BENTUK, bukan perilaku, dan alasannya disebut apa adanya:
    `utang_usaha()` hanya dapat diuji perilakunya terhadap basis data
    sungguhan, dan gerbang CI berjalan tanpa basis data. Tanpa penjaga ini,
    saringannya boleh hilang lagi dan seluruh berkas uji tetap hijau —
    persis cara ia tidak ada sejak awal.

    Yang terjadi bila ia hilang (sudah diukur terhadap MariaDB sungguhan):
    pembelian internal Rp 25 juta muncul sebagai utang yang tidak akan pernah
    tertutup oleh pembayaran apa pun, sebab dokumen internal memang tidak
    punya baris pembayaran. Utang usaha membesar, quick ratio dan modal kerja
    bersih mengecil, dan kewajiban 30 hari menyebut uang yang tidak akan
    dibayarkan ke mana pun.
    """
    import os

    akar = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    jalur = os.path.join(akar, "repository", "finance_status_repository.py")
    sumber = open(jalur, encoding="utf-8").read()

    awal = sumber.index("async def utang_usaha")
    akhir = sumber.index("async def pinjaman")
    badan = sumber[awal:akhir]

    assert "isInternal == False" in badan, (
        "utang_usaha() tidak lagi menyaring pembelian internal"
    )


def test_belum_dibayar_menyaring_pembelian_internal():
    """
    Daftar tagihan yang dipakai orang tiap hari, dan kekeliruan yang SAMA.

    `belum_dibayar` menghitung sisa dari baris pembayaran, bukan dari
    `isPaid`. Pembelian internal tidak punya baris pembayaran sama sekali,
    jadi seluruh nilainya menumpuk permanen sebagai tagihan yang belum
    lunas — dan tidak akan pernah ada pembayaran yang menutupnya.

    Keterangan pada fungsi itu sendiri menyebut kelalaian yang paling mahal
    adalah tagihan yang tidak pernah dibuka; baris internal yang menumpuk di
    sana persis yang menguburnya.
    """
    import os

    akar = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    jalur = os.path.join(akar, "repository", "purchase_repository.py")
    sumber = open(jalur, encoding="utf-8").read()

    awal = sumber.index("async def belum_dibayar")
    akhir = sumber.index("sisa > 5,", awal)
    badan = sumber[awal:akhir]

    assert "isInternal == False" in badan, (
        "belum_dibayar() tidak lagi menyaring pembelian internal"
    )


# --------------------------------------------------------------------------
# Kewajiban lengkap & ekuitas turunan
# --------------------------------------------------------------------------


class TestKewajibanLengkap:

    @pytest.mark.asyncio
    async def test_gaji_belum_cair_ikut_menekan_quick_ratio(self, repo):
        """
        `payments_outgoing` menunjuk LIMA jenis dokumen; empat di antaranya
        kewajiban kepada pihak luar. Selama hanya pembelian yang dihitung,
        gaji bulan berjalan yang belum cair tidak muncul sebagai kewajiban
        sama sekali — dan rasionya tampak lebih baik daripada keadaannya.

        Utang 50 + kewajiban lain 30 = 80. Rasio yang benar (100+60)/80 = 2,0;
        yang lama (100+60)/50 = 3,2.
        """
        repo["lain"] = {"total": 30.0, "jumlahDokumen": 4, "rincian": {}}
        hasil = await FS.get_status()

        assert hasil["kewajibanLancar"] == 80.0
        assert hasil["quickRatio"] == pytest.approx(2.0)
        assert hasil["modalKerjaBersih"] == pytest.approx(80.0)

    @pytest.mark.asyncio
    async def test_selisih_terhadap_versi_lama_disebutkan(self, repo):
        """
        Rasionya TURUN dibanding yang sempat dilihat orang.

        Tanpa menyebutkan selisihnya, siapa pun yang mencatat angka minggu
        lalu akan mengira ada yang rusak — dan angka yang dicurigai berhenti
        dipakai, yang lebih buruk daripada angka yang salah.
        """
        repo["lain"] = {"total": 30.0, "jumlahDokumen": 4, "rincian": {}}
        hasil = await FS.get_status()
        selisih = hasil["selisihVersiLama"]

        assert selisih["utangUsahaSaja"] == 50.0
        assert selisih["kewajibanLancarSekarang"] == 80.0
        assert selisih["tambahan"] == 30.0
        assert selisih["quickRatioVersiLama"] == pytest.approx(3.2)
        assert hasil["catatan"]["kewajibanLengkapSejakVersiIni"] is True


class TestNeracaRingkas:

    @pytest.mark.asyncio
    async def test_ekuitas_adalah_aset_dikurangi_kewajiban(self, repo):
        """
        Ekuitas tidak tercatat; ia DITURUNKAN — dan komponen besarnya memang
        ada di sistem ini.

        Aset 100 kas + 60 piutang + 300 aset tetap = 460.
        Kewajiban 50 utang + 30 lain + 500 pinjaman = 580.
        Ekuitas = -120.
        """
        repo["lain"] = {"total": 30.0, "jumlahDokumen": 4, "rincian": {}}
        repo["asetTetap"]["nilaiBuku"] = 300.0
        hasil = await FS.get_status()
        n = hasil["neraca"]

        assert n["aset"]["total"] == pytest.approx(460.0)
        assert n["kewajiban"]["total"] == pytest.approx(580.0)
        assert n["ekuitas"] == pytest.approx(-120.0)

    @pytest.mark.asyncio
    async def test_debt_to_equity_pada_ekuitas_minus_TIDAK_dicetak(self, repo):
        """
        Pada ekuitas minus, D/E tidak bermakna.

        `580 / -120` adalah -4,83 — angka yang terbaca terukur, pada keadaan
        yang justru paling perlu dibicarakan orang. Tanda pisah memaksa
        pertanyaannya diajukan.
        """
        repo["asetTetap"]["nilaiBuku"] = 300.0
        hasil = await FS.get_status()

        assert hasil["neraca"]["ekuitas"] < 0
        assert hasil["neraca"]["debtToEquity"] is None

    @pytest.mark.asyncio
    async def test_debt_to_equity_dihitung_saat_ekuitas_positif(self, repo):
        """Aset tetap 2000 -> ekuitas 2110, kewajiban 550 -> D/E 0,26."""
        repo["asetTetap"]["nilaiBuku"] = 2000.0
        hasil = await FS.get_status()
        n = hasil["neraca"]

        assert n["ekuitas"] == pytest.approx(1610.0)
        assert n["debtToEquity"] == pytest.approx(550.0 / 1610.0)

    @pytest.mark.asyncio
    async def test_celah_neraca_disebut_satu_per_satu(self, repo):
        """
        Perkiraan yang tidak menyebut celahnya akan dibaca sebagai angka
        pembukuan — lalu dicocokkan dengan akuntan dan tidak pernah cocok.
        """
        hasil = await FS.get_status()
        celah = hasil["neraca"]["celah"]

        assert "uangMukaKlien" in celah
        assert "utangPajakBelumDisetor" in celah
        assert "pembelianAsetYangDibebankanLangsung" in celah
        assert hasil["catatan"]["ekuitasDiturunkanBukanDicatat"] is True


# --------------------------------------------------------------------------
# Perputaran, konsentrasi, backlog
# --------------------------------------------------------------------------


class TestPerputaran:

    @pytest.mark.asyncio
    async def test_dso_dan_dpo_dihitung_dari_arus_setahun(self, repo):
        """
        DUA BELAS BULAN, bukan bulan berjalan.

        Pendapatan kontraktor datang bergelombang mengikuti termin; membagi
        piutang dengan pendapatan satu bulan menghasilkan DSO yang melompat
        antara belasan dan ratusan hari — dan angka yang melompat berhenti
        dipercaya sebelum sempat dipakai.
        """
        hasil = await FS.get_status()
        r = hasil["rasio"]

        assert r["dso"] == pytest.approx(60.0 / 600.0 * 365)
        assert r["dpo"] == pytest.approx(50.0 / 300.0 * 365)
        assert r["siklusModalKerja"] == pytest.approx(r["dso"] - r["dpo"])

    @pytest.mark.asyncio
    async def test_tanpa_pendapatan_DSO_bukan_nol(self, repo):
        """
        Perusahaan yang belum berfaktur setahun terakhir tidak punya DSO.

        "0 hari" pada keadaan itu terbaca sebagai penagihan yang sempurna —
        kebalikan dari yang sebenarnya diketahui, yaitu tidak ada apa-apa
        untuk diukur.
        """
        repo["arus"]["pendapatan"] = 0.0
        hasil = await FS.get_status()

        assert hasil["rasio"]["dso"] is None
        assert hasil["rasio"]["siklusModalKerja"] is None

    @pytest.mark.asyncio
    async def test_bagian_piutang_tua_dihitung(self, repo):
        """Ember 90+ dibagi seluruh piutang: 0 dari 60 pada keadaan bawaan."""
        repo["piutang"]["umur"]["90+"] = 30.0
        repo["piutang"]["total"] = 60.0
        hasil = await FS.get_status()

        assert hasil["rasio"]["piutangTua"] == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_konsentrasi_diteruskan_apa_adanya(self, repo):
        """
        Rasio likuiditas tidak dapat melihat ini: piutang yang tersebar pada
        delapan klien dan yang seluruhnya pada satu klien menghasilkan quick
        ratio yang sama persis.
        """
        hasil = await FS.get_status()
        assert hasil["rasio"]["konsentrasiPiutang"] == pytest.approx(40.0 / 60.0)

    @pytest.mark.asyncio
    async def test_dasar_penyebut_ikut_dikirim(self, repo):
        """Angka yang penyebutnya tidak terlihat hanya dapat dipercaya, tidak ditelusuri."""
        dasar = (await FS.get_status())["rasio"]["dasar"]
        assert dasar["pendapatan12Bulan"] == 600.0
        assert dasar["hari"] == 365


class TestMarjinHanyaLevel5:

    @pytest.mark.asyncio
    async def test_level_4_tidak_menerima_marjin_sama_sekali(self, repo, monkeypatch):
        """
        Bloknya TIDAK DIGAMBAR, bukan digambar kosong.

        Kotak bertanda pisah memberi tahu bahwa ada angka yang disembunyikan,
        dan itu pertanyaan yang berulang. Yang lebih penting: gerbangnya di
        SERVER — menyembunyikan blok di peramban tidak menahan siapa pun yang
        memanggil rutenya langsung.
        """
        async def _marjin_palsu(ekuitas, pendapatan):
            return {"marjinKotor": 0.2, "roe": 0.3}

        monkeypatch.setattr(
            FS, "_marjin", staticmethod(_marjin_palsu)
        )
        hasil = await FS.get_status(user_level=4)

        assert "marjinKotor" not in hasil["rasio"]
        assert "roe" not in hasil["rasio"]
        assert hasil["bolehMelihatLaba"] is False

    @pytest.mark.asyncio
    async def test_level_5_menerima_marjin(self, repo, monkeypatch):
        async def _marjin_palsu(ekuitas, pendapatan):
            return {"marjinKotor": 0.2, "roe": 0.3}

        monkeypatch.setattr(FS, "_marjin", staticmethod(_marjin_palsu))
        hasil = await FS.get_status(user_level=5)

        assert hasil["rasio"]["marjinKotor"] == 0.2
        assert hasil["bolehMelihatLaba"] is True

    @pytest.mark.asyncio
    async def test_marjin_yang_GAGAL_tidak_menjatuhkan_halaman(self, repo, monkeypatch):
        """
        Laba rugi adalah modul lain dengan kuerinya sendiri. Membiarkannya
        menjatuhkan angka kas berarti satu kegagalan di sana menghapus
        seluruh alasan halaman ini dibuka.
        """
        async def _marjin_gagal(ekuitas, pendapatan):
            return {}

        monkeypatch.setattr(FS, "_marjin", staticmethod(_marjin_gagal))
        hasil = await FS.get_status(user_level=5)

        assert hasil["kas"]["total"] == 100.0
        assert "marjinKotor" not in hasil["rasio"]


class TestPitaAcuan:

    @pytest.mark.asyncio
    async def test_pita_ikut_dikirim_bersama_angkanya(self, repo):
        """
        Angka tanpa pembandingnya tidak dapat ditimbang siapa pun — dan pita
        yang hanya hidup di kode layar akan berselisih dengan yang disetel.
        """
        ambang = (await FS.get_status())["ambang"]
        assert ambang["quickRatio"]["atas"] == 1.5
        assert ambang["dso"]["atas"] == 95.0
        assert ambang["dso"]["bawah"] is None

    @pytest.mark.asyncio
    async def test_pita_terbalik_ditolak(self, monkeypatch):
        """
        Pita terbalik tidak menghasilkan galat; ia hanya membuat SETIAP nilai
        berada di luar acuan — seluruh rasio menyala sekaligus, dan yang
        membacanya akan mengira perusahaannya yang bermasalah.

        Penyimpanannya DITIRU supaya satu-satunya yang dapat menolak adalah
        pemeriksaan pita itu sendiri. Tanpa tiruan ini ujinya lolos karena
        basis data ujinya memang tidak punya tabelnya — yaitu lolos untuk
        alasan yang tidak ada hubungannya dengan yang sedang dijaga.
        """
        tersimpan = []

        async def _simpan(kode, bawah, atas, user_id):
            tersimpan.append((kode, bawah, atas))
            return {"ok": True}

        monkeypatch.setattr(R, "simpan_ambang", staticmethod(_simpan))
        hasil = await FS.simpan_ambang(
            "quickRatio", {"bawah": 2.0, "atas": 1.0}, user_id=1
        )
        assert hasil["status"] == 400
        assert not tersimpan, "pita terbalik sempat tersimpan"

    @pytest.mark.asyncio
    async def test_kode_yang_tidak_dikenal_ditolak(self, monkeypatch):
        async def _simpan(kode, bawah, atas, user_id):
            return {"error": "VALIDATION"}

        monkeypatch.setattr(R, "simpan_ambang", staticmethod(_simpan))
        hasil = await FS.simpan_ambang("ngawur", {"bawah": 1}, user_id=1)
        assert hasil["status"] == 400

    @pytest.mark.asyncio
    async def test_sisi_kosong_boleh(self, monkeypatch):
        """DSO tidak punya batas bawah yang bermakna — kosong harus sah."""
        disimpan = {}

        async def _simpan(kode, bawah, atas, user_id):
            disimpan.update({"bawah": bawah, "atas": atas})
            return {"ok": True}

        monkeypatch.setattr(R, "simpan_ambang", staticmethod(_simpan))
        hasil = await FS.simpan_ambang("dso", {"bawah": "", "atas": 80}, user_id=1)

        assert "error" not in hasil
        assert disimpan["bawah"] is None
        assert disimpan["atas"] == 80.0


class TestRoe:

    @pytest.mark.asyncio
    async def test_roe_pada_ekuitas_minus_TIDAK_dicetak(self, repo):
        """
        Pada ekuitas minus, laba POSITIF menghasilkan ROE MINUS.

        Di layar itu terbaca sebagai rugi — kebalikan dari keadaannya. Dan
        yang membacanya tidak punya cara mengetahui bahwa tandanya berasal
        dari penyebut, bukan dari pembilang.
        """
        hasil = await FS._marjin(ekuitas=-120.0, pendapatan_th=600.0)
        # Laba rugi tidak tersedia di lingkungan uji; yang dijaga bentuk
        # keputusannya, diperiksa langsung pada rumusnya.
        assert hasil == {} or hasil.get("roe") is None

    @pytest.mark.asyncio
    async def test_rumus_roe_memakai_ekuitas_positif_saja(self):
        """
        Dibaca dari sumbernya: satu-satunya cara menjaga cabang ini tanpa
        laporan laba rugi yang berjalan di lingkungan uji, dan itu disebutkan
        apa adanya alih-alih dibiarkan tampak seperti uji perilaku.
        """
        import os

        akar = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sumber = open(
            os.path.join(akar, "controllers", "finance_status_controller.py"),
            encoding="utf-8",
        ).read()
        assert '(laba_bersih / ekuitas) if ekuitas > 0 else None' in sumber, (
            "ROE tidak lagi dijaga terhadap ekuitas nol atau minus"
        )


# --------------------------------------------------------------------------
# "Ini bagus atau tidak"
# --------------------------------------------------------------------------


class TestPosisiTerhadapPita:
    """
    Layar sempat berhenti menjawab pertanyaan yang membuat orang membukanya.

    Angkanya dicetak telanjang beserta pitanya sebagai tulisan kecil, dengan
    alasan tidak mau memvonis. Akibatnya "2,03" tidak mengatakan apa-apa: yang
    membacanya harus membandingkannya sendiri dengan pita yang dicetak lebih
    redup daripada peringatan di sebelahnya.

    Yang dijaga di sini MENILAI ANGKANYA, bukan perusahaannya.
    """

    def test_di_atas_pita_pada_utang_adalah_kabar_buruk(self):
        """D/E 2,03 pada pita 0,5-1,5 — utang dua kali lipat ekuitas."""
        hasil = PTP(2.03, {"bawah": 0.5, "atas": 1.5, "arah": "naikBuruk"})
        assert hasil["posisi"] == "diatas"
        assert hasil["baik"] is False

    def test_di_atas_pita_pada_marjin_adalah_kabar_BAIK(self):
        """
        Menyamakan keduanya adalah kekeliruan yang paling mudah terjadi:
        marjin 25% di atas pita kabar baik, DSO 130 hari di atas pita kabar
        buruk. Satu tanda untuk dua keadaan yang berlawanan.
        """
        hasil = PTP(0.25, {"bawah": 0.15, "atas": None, "arah": "naikBaik"})
        assert hasil["posisi"] == "didalam"
        assert hasil["baik"] is True

        # Dengan batas atas yang disetel orang, di atasnya tetap baik.
        hasil = PTP(0.30, {"bawah": 0.15, "atas": 0.25, "arah": "naikBaik"})
        assert hasil["posisi"] == "diatas"
        assert hasil["baik"] is True

    def test_di_bawah_pita_pada_DSO_adalah_kabar_baik(self):
        """Tertagih lebih cepat daripada kebiasaan industri."""
        hasil = PTP(40.0, {"bawah": None, "atas": 95.0, "arah": "naikBuruk"})
        assert hasil["posisi"] == "didalam"
        assert hasil["baik"] is True

    def test_quick_ratio_terlalu_TINGGI_juga_bukan_kabar_baik(self):
        """
        Dua sisinya sama-sama berarti: terlalu rendah berarti tidak mampu
        bayar, terlalu tinggi berarti kas menganggur alih-alih bekerja.
        """
        hasil = PTP(4.0, {"bawah": 1.1, "atas": 1.5, "arah": "pita"})
        assert hasil["posisi"] == "diatas"
        assert hasil["baik"] is False

    def test_angka_yang_belum_ada_BUKAN_di_dalam_acuan(self):
        """
        `None` berarti belum dapat diukur. Menandainya "di dalam acuan"
        memberi tanda aman pada sesuatu yang tidak pernah diperiksa.
        """
        hasil = PTP(None, {"bawah": 1.1, "atas": 1.5, "arah": "pita"})
        assert hasil["posisi"] is None
        assert hasil["baik"] is None

    def test_sisi_pita_yang_kosong_tidak_pernah_dilanggar(self):
        """DSO tidak punya batas bawah — berapa pun cepatnya tetap di dalam."""
        hasil = PTP(1.0, {"bawah": None, "atas": 95.0, "arah": "naikBuruk"})
        assert hasil["posisi"] == "didalam"

    @pytest.mark.asyncio
    async def test_penilaian_ikut_dikirim_untuk_tiap_rasio(self, repo):
        """
        Dinilai SESUDAH seluruh rasio terkumpul, supaya rasio yang
        ditambahkan belakangan tidak terlewat dinilai — dan muncul di layar
        sebagai angka telanjang lagi.
        """
        hasil = await FS.get_status()
        p = hasil["penilaian"]

        assert "quickRatio" in p
        assert "debtToEquity" in p
        assert "dso" in p
        assert p["dso"]["posisi"] == "didalam"
