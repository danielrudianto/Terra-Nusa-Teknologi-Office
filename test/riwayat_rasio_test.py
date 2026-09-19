"""
RIWAYAT RASIO: rasio likuiditas & penagihan ditarik mundur per bulan.

Satu halaman yang seluruhnya dapat salah tanpa melempar apa pun.

Kekeliruan yang paling mungkin, dan paling sulit dilihat, adalah SUMBER YANG
LUPA DIBERI TANGGAL. Bila satu saja dari delapan sumber dipanggil tanpa
`pada`, ia menjawab dengan keadaan HARI INI untuk setiap titik bulan —
garisnya mendatar sempurna, tidak ada galat, tidak ada nilai kosong, dan
yang melihatnya menyimpulkan perusahaannya stabil selama setahun. Itulah
yang dijaga paling keras di berkas ini.

Yang kedua: rumus di `_potret` menyimpang dari rumus di `get_status`. Kalau
itu terjadi, titik TERAKHIR grafik tidak akan sama dengan angka besar yang
tercetak di atasnya pada halaman yang sama, dan yang membacanya akan
mengira salah satunya rusak tanpa tahu yang mana.
"""

from datetime import date, timedelta

import pytest

from controllers.finance_status_controller import FinanceStatusController as FS
from repository.finance_status_repository import (
    AMBANG_BAWAAN as R_AMBANG,
    FinanceStatusRepository as R,
)


# --------------------------------------------------------------------------
# Titik bulan
# --------------------------------------------------------------------------


def _titik(hari_ini: date, mundur: int):
    """Panggil `_titik_bulan` dengan "hari ini" yang ditentukan."""
    import controllers.finance_status_controller as modul

    asli = modul.d

    class TanggalPalsu(date):
        @classmethod
        def today(cls):
            return hari_ini

    modul.d = TanggalPalsu
    try:
        return FS._titik_bulan(mundur)
    finally:
        modul.d = asli


def test_titik_urut_kronologis_dan_sebanyak_bulannya():
    """
    Urutannya dari yang terlama ke yang terbaru.

    Terbalik, grafiknya menggambar perbaikan sebagai pemburukan — dan
    sebaliknya. Tidak ada yang akan mengira grafiknya salah; yang dikira
    salah adalah perusahaannya.
    """
    titik = _titik(date(2026, 9, 19), mundur=12)
    assert len(titik) == 12
    assert titik == sorted(titik)
    assert titik[-1] == date(2026, 9, 19)
    assert titik[0] == date(2025, 10, 31)


def test_titik_terakhir_adalah_hari_ini_bukan_akhir_bulan():
    """
    Bulan berjalan dipotret HARI INI.

    Akhir bulan berjalan belum terjadi. Memakainya berarti membandingkan
    posisi hari ini dengan tanggal yang belum ada dokumennya — dan titik
    terakhirnya tidak akan sama dengan angka di halaman utama.
    """
    titik = _titik(date(2026, 9, 19), mundur=3)
    assert titik[-1] == date(2026, 9, 19)
    assert titik[-2] == date(2026, 8, 31)
    assert titik[-3] == date(2026, 7, 31)


def test_titik_melewati_pergantian_tahun():
    """Mundur 6 bulan dari Februari harus sampai September tahun lalu."""
    titik = _titik(date(2026, 2, 10), mundur=6)
    assert titik[0] == date(2025, 9, 30)
    assert titik[-1] == date(2026, 2, 10)


def test_akhir_februari_tahun_kabisat():
    """
    29 Februari 2028, bukan 28.

    Akhir bulan dihitung sebagai sehari sebelum awal bulan berikutnya justru
    supaya kabisat tidak perlu diurus sendiri. Diuji agar cara itu tidak
    diganti dengan tabel 28/30/31 di kemudian hari.
    """
    titik = _titik(date(2028, 4, 5), mundur=3)
    assert titik[0] == date(2028, 2, 29)


def test_desember_tidak_menjadi_bulan_ketigabelas():
    titik = _titik(date(2027, 1, 20), mundur=2)
    assert titik[0] == date(2026, 12, 31)


# --------------------------------------------------------------------------
# Potret
# --------------------------------------------------------------------------


@pytest.fixture
def sumber(monkeypatch):
    """
    Tiru kedelapan sumber, dan CATAT tanggal yang diterima masing-masing.

    Pencatatan itu bukan hiasan: ia satu-satunya cara membuktikan tiap
    sumber benar-benar dibatasi tanggalnya, karena sumber yang lupa dibatasi
    tetap menjawab dengan bentuk yang sah.
    """
    dipanggil: dict = {}
    # Keadaan boleh dibuat bergantung tanggal oleh uji yang membutuhkannya.
    keadaan = {
        "kas": lambda p: {"total": 100.0, "dikecualikan": 0.0},
        "piutang": lambda p: {
            "total": 60.0,
            "umur": {"0-30": 45.0, "31-60": 0.0, "61-90": 0.0, "90+": 15.0},
        },
        "utang": lambda p: {"total": 50.0, "tempo": {}},
        "pinjaman": lambda p: {"total": 500.0},
        "lain": lambda p: {"total": 0.0, "rincian": {}},
        "aset": lambda p: {"nilaiBuku": 700.0},
        "arus": lambda p: {
            "pendapatan": 600.0,
            "pembelian": 300.0,
            "hari": 365,
        },
        "konsentrasi": lambda p: {
            "total": 60.0,
            "terbesar": {"clientID": 1, "sisa": 40.0},
        },
    }

    def _pasang(nama_repo: str, kunci: str):
        async def _f(pada=None):
            dipanggil.setdefault(kunci, []).append(pada)
            return keadaan[kunci](pada)

        monkeypatch.setattr(R, nama_repo, staticmethod(_f))

    _pasang("total_kas", "kas")
    _pasang("piutang", "piutang")
    _pasang("utang_usaha", "utang")
    _pasang("pinjaman", "pinjaman")
    _pasang("kewajiban_lain", "lain")
    _pasang("nilai_buku_aset", "aset")
    _pasang("arus_setahun", "arus")
    _pasang("konsentrasi_piutang", "konsentrasi")

    async def _ambang():
        return dict(R_AMBANG)

    monkeypatch.setattr(R, "ambang", staticmethod(_ambang))
    return {"keadaan": keadaan, "dipanggil": dipanggil}


@pytest.mark.asyncio
async def test_setiap_sumber_menerima_tanggal_titiknya(sumber):
    """
    INI PENJAGA UTAMANYA.

    Kedelapan sumber harus menerima tanggal, dan tanggal yang SAMA dengan
    titik yang sedang dipotret. Satu sumber yang terlewat membuat garisnya
    mendatar tanpa satu pun tanda bahwa ada yang salah.
    """
    hasil = await FS.riwayat(3)
    tanggal_titik = [date.fromisoformat(t["tanggal"]) for t in hasil["titik"]]

    for kunci in (
        "kas",
        "piutang",
        "utang",
        "pinjaman",
        "lain",
        "aset",
        "arus",
        "konsentrasi",
    ):
        assert kunci in sumber["dipanggil"], f"{kunci} tidak pernah dipanggil"
        diterima = sumber["dipanggil"][kunci]
        assert None not in diterima, f"{kunci} dipanggil tanpa tanggal"
        assert diterima == tanggal_titik, f"{kunci} menerima tanggal yang salah"


@pytest.mark.asyncio
async def test_titik_hasil_urut_dari_terlama_ke_hari_ini(sumber):
    """
    Urutan pada HASILNYA, bukan hanya pada daftar tanggalnya.

    `_titik_bulan` boleh benar sementara perakitannya membalik — dan grafik
    yang terbalik menggambar perbaikan sebagai pemburukan. Yang dikira salah
    bukan grafiknya, melainkan perusahaannya.
    """
    hasil = await FS.riwayat(5)
    tanggal = [date.fromisoformat(t["tanggal"]) for t in hasil["titik"]]
    assert tanggal == sorted(tanggal)
    assert tanggal[-1] == date.today()


@pytest.mark.asyncio
async def test_garis_bergerak_ketika_datanya_bergerak(sumber):
    """
    Bukti bahwa tanggalnya benar-benar dipakai, dari sisi hasilnya.

    Uji di atas memeriksa pemanggilannya; yang ini memeriksa angkanya.
    Keduanya perlu: sumber dapat menerima tanggal lalu mengabaikannya.
    """
    sumber["keadaan"]["piutang"] = lambda p: {
        # Piutang naik seiring waktu — jadi DSO harus naik juga.
        "total": float(p.toordinal() % 1000),
        "umur": {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0},
    }
    hasil = await FS.riwayat(4)
    dso = [t["dso"] for t in hasil["titik"]]
    assert len(set(dso)) > 1, "DSO mendatar padahal piutangnya berubah"


@pytest.mark.asyncio
async def test_rumus_titik_terakhir_sama_dengan_halaman_utama(sumber):
    """
    Titik terakhir harus sama dengan angka besar di halaman yang sama.

    Rumusnya disalin ke `_potret`; salinan yang menyimpang menghasilkan dua
    angka berbeda untuk hari yang sama, di layar yang sama.
    """
    hasil = await FS.riwayat(1)
    t = hasil["titik"][-1]

    kas, piutang, utang, lain, pinjaman, aset = 100.0, 60.0, 50.0, 0.0, 500.0, 700.0
    kewajiban_lancar = utang + lain
    ekuitas = (kas + piutang + aset) - (kewajiban_lancar + pinjaman)

    assert t["quickRatio"] == pytest.approx((kas + piutang) / kewajiban_lancar)
    assert t["debtToEquity"] == pytest.approx(
        (kewajiban_lancar + pinjaman) / ekuitas
    )
    assert t["dso"] == pytest.approx(piutang / 600.0 * 365)
    assert t["dpo"] == pytest.approx(utang / 300.0 * 365)
    assert t["siklusModalKerja"] == pytest.approx(t["dso"] - t["dpo"])
    assert t["piutangTua"] == pytest.approx(15.0 / 60.0)
    assert t["konsentrasiPiutang"] == pytest.approx(40.0 / 60.0)
    assert t["ekuitas"] == pytest.approx(ekuitas)


@pytest.mark.asyncio
async def test_ekuitas_minus_mengosongkan_dte_dan_menandainya(sumber):
    """
    Pada ekuitas minus, D/E tidak bermakna — dan `null` saja tidak cukup.

    Tanpa penanda, layar tidak dapat membedakan "bulan itu belum ada
    datanya" dari "bulan itu ekuitasnya minus", dan yang kedua justru
    keadaan yang paling perlu terlihat.
    """
    sumber["keadaan"]["aset"] = lambda p: {"nilaiBuku": 0.0}
    sumber["keadaan"]["pinjaman"] = lambda p: {"total": 5000.0}
    hasil = await FS.riwayat(2)
    for t in hasil["titik"]:
        assert t["ekuitas"] < 0
        assert t["debtToEquity"] is None
        assert t["ekuitasMinus"] is True


@pytest.mark.asyncio
async def test_penyebut_nol_menghasilkan_kosong_bukan_nol(sumber):
    """
    Bulan tanpa pendapatan tidak punya DSO — dan "0 hari" pada keadaan itu
    terbaca sebagai penagihan yang sempurna.
    """
    sumber["keadaan"]["arus"] = lambda p: {
        "pendapatan": 0.0,
        "pembelian": 0.0,
        "hari": 365,
    }
    sumber["keadaan"]["utang"] = lambda p: {"total": 0.0, "tempo": {}}
    sumber["keadaan"]["lain"] = lambda p: {"total": 0.0, "rincian": {}}
    hasil = await FS.riwayat(1)
    t = hasil["titik"][0]
    assert t["dso"] is None
    assert t["dpo"] is None
    assert t["siklusModalKerja"] is None
    assert t["quickRatio"] is None


@pytest.mark.asyncio
async def test_mundur_dibatasi_atas_dan_bawah(sumber):
    """
    `?mundur=999` memindai seluruh riwayat; `?mundur=0` menghasilkan grafik
    kosong yang terbaca sebagai tidak ada data.
    """
    banyak = await FS.riwayat(999)
    assert banyak["mundur"] == FS.MAKS_MUNDUR
    assert len(banyak["titik"]) == FS.MAKS_MUNDUR

    kosong = await FS.riwayat(0)
    assert kosong["mundur"] == 1
    assert len(kosong["titik"]) == 1


@pytest.mark.asyncio
async def test_marjin_tidak_ikut_ditarik_mundur(sumber):
    """
    Marjin sengaja TIDAK ada di riwayat, dan alasannya harus ikut terkirim.

    Beban dicatat menurut tanggal dokumen, bukan tanggal kejadiannya; marjin
    masa lalu karena itu berubah setiap kali nota lama diinput hari ini.
    Garis yang berubah sendiri berhenti dipercaya.
    """
    hasil = await FS.riwayat(2)
    assert "marjinKotor" not in hasil["rasio"]
    assert "roe" not in hasil["rasio"]
    assert hasil["catatan"]["marjinTidakDitarikMundur"] is True
    for t in hasil["titik"]:
        assert "marjinKotor" not in t


@pytest.mark.asyncio
async def test_batasan_kas_lampau_disebut(sumber):
    """
    Kas bulan lampau DIREKONSTRUKSI dari mutasi, bukan dibaca dari saldo.

    Batasan yang hanya ditulis di komentar kode tidak pernah sampai ke yang
    membaca angkanya.
    """
    hasil = await FS.riwayat(2)
    assert hasil["catatan"]["kasLampauDirekonstruksiDariMutasi"] is True
    assert hasil["catatan"]["titikTerakhirAdalahHariIni"] is True


@pytest.mark.asyncio
async def test_kegagalan_satu_sumber_tidak_mengembalikan_angka_karangan(
    sumber, monkeypatch
):
    """
    Sumber yang melempar harus menghasilkan galat, BUKAN titik bernilai nol.

    Titik nol pada grafik rasio terbaca sebagai perusahaan yang kehabisan
    kas pada bulan itu.
    """

    async def _meledak(pada=None):
        raise RuntimeError("basis data tidak dapat dibaca")

    monkeypatch.setattr(R, "piutang", staticmethod(_meledak))
    hasil = await FS.riwayat(2)
    assert "error" in hasil
    assert "titik" not in hasil


# --------------------------------------------------------------------------
# Kas yang tidak terbaca
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kas_yang_gagal_dibaca_dikosongkan_bukan_dinolkan(sumber):
    """
    INI YANG PALING BERBAHAYA DI SELURUH FITUR INI.

    Saldo bulan lampau tidak tercatat di mana pun; ia DISUSUN ULANG dari view
    `mutation`. `total_kas` menangkap seluruh galat dan mengembalikan nol —
    jadi bila view itu tidak ada di sebuah lingkungan, SELURUH titik lampau
    berkas nol sekaligus.

    Yang tergambar: quick ratio jatuh ke dasar dan ekuitas minus sepanjang
    tahun lalu, lalu pulih mendadak pada titik terakhir (yang memakai saldo
    tercatat, bukan rekonstruksi). Grafik itu menceritakan kebangkrutan yang
    tidak pernah terjadi, tanpa satu pun galat di layar.

    Karena itu nol yang berarti "tidak terbaca" harus dapat dibedakan dari
    nol yang berarti "memang tidak ada uang".
    """
    sumber["keadaan"]["kas"] = lambda p: {
        "total": 0.0,
        "dikecualikan": 0.0,
        "jumlahDikecualikan": 0,
        "gagal": True,
    }
    hasil = await FS.riwayat(2)
    for t in hasil["titik"]:
        assert t["kasTidakTerbaca"] is True
        assert t["kas"] is None, "kas yang gagal dibaca tergambar sebagai nol"
        assert t["quickRatio"] is None
        assert t["debtToEquity"] is None
        assert t["ekuitas"] is None
        # Ekuitas minus adalah PERNYATAAN tentang keadaan perusahaan; ia
        # tidak boleh dinyatakan atas angka yang tidak terbaca.
        assert t["ekuitasMinus"] is False


@pytest.mark.asyncio
async def test_yang_tidak_bergantung_kas_tetap_digambar(sumber):
    """
    Satu sumber yang gagal tidak menghapus yang lain.

    DSO, DPO, piutang tua, dan konsentrasi tidak menyentuh saldo kas sama
    sekali. Mengosongkannya juga berarti membuang angka yang benar karena
    sumber lain yang gagal — dan grafik yang kosong tanpa sebab sama tidak
    berguna dengan grafik yang salah.
    """
    sumber["keadaan"]["kas"] = lambda p: {"total": 0.0, "gagal": True}
    hasil = await FS.riwayat(1)
    t = hasil["titik"][0]
    assert t["dso"] is not None
    assert t["dpo"] is not None
    assert t["piutangTua"] is not None
    assert t["konsentrasiPiutang"] is not None


@pytest.mark.asyncio
async def test_kas_nol_yang_MEMANG_nol_tetap_digambar_sebagai_nol(sumber):
    """
    Sisi sebaliknya, dan sama pentingnya.

    Rekening yang benar-benar kosong harus tergambar kosong. Kalau penandanya
    dipasang terlalu longgar — misalnya "nol berarti gagal" — keadaan yang
    paling perlu terlihat justru yang disembunyikan.
    """
    sumber["keadaan"]["kas"] = lambda p: {
        "total": 0.0,
        "dikecualikan": 0.0,
        "jumlahDikecualikan": 0,
    }
    hasil = await FS.riwayat(1)
    t = hasil["titik"][0]
    assert t["kasTidakTerbaca"] is False
    assert t["kas"] == 0.0
    assert t["quickRatio"] is not None
