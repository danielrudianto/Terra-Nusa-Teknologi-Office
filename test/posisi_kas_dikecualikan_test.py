"""
Posisi kas di beranda tidak menghitung rekening yang dikecualikan.

APA YANG SALAH SEBELUMNYA

`excludeFromCalendar` dibuat untuk rekening yang uangnya BUKAN kas yang dapat
dipakai — deposit jaminan, uang muka yang dititipkan. Kalender menghormatinya.
`dashboard/cash-position` tidak: kueri rekeningnya hanya menyaring `isDelete`,
sehingga Total Saldo di beranda memuat uang yang tidak dapat dibelanjakan.

Kegagalannya tidak menghasilkan galat apa pun, dan angkanya tetap masuk akal —
hanya terlalu besar. Dua layar menyebut "saldo" dengan arti yang berbeda, dan
tidak ada satu tempat pun yang menyebut selisihnya.

KENAPA DIUJI LEWAT ARITMETIKANYA, BUKAN SQL-NYA

Menyaringnya di SQL (`AND excludeFromCalendar = 0`) akan MEMBUANG rekeningnya
dari jawaban. Uang di rekening jaminan tetap uang; membuangnya berarti
satu-satunya layar yang menyebut saldo rekening berhenti menyebutnya, dan saldo
yang tidak pernah ditampilkan adalah saldo yang tidak pernah dicocokkan.

Jadi yang dijaga di sini: barisnya TETAP ADA, tetapi tidak masuk `totalBalance`,
dan selisihnya dilaporkan sehingga penjumlahannya dapat dicocokkan.
"""

import datetime as dt

import pytest

from models import dashboard_model as modul
from models.dashboard_model import DashboardModel


class _Baris:
    """Meniru baris `databases` — `Row` SQLAlchemy.

    Sudah diperiksa terhadap MariaDB sungguhan: `baris["kolom"]` MAUPUN
    `getattr(baris, "kolom")` keduanya berlaku, dan `getattr` dengan nama yang
    tidak ada mengembalikan nilai bawaannya. Keduanya ditiru di sini supaya
    tiruan ini tidak lebih permisif daripada yang sebenarnya.
    """

    def __init__(self, **kolom):
        self.__dict__.update(kolom)

    def __getitem__(self, kunci):
        return self.__dict__[kunci]


class _Db:
    """Menggantikan `database`; membalas menurut tabel yang disebut kuerinya."""

    def __init__(self, mutasi, rekening):
        self.mutasi = mutasi
        self.rekening = rekening
        self.sql = []

    async def fetch_all(self, kueri, nilai=None):
        teks = " ".join(str(kueri).split())
        self.sql.append(teks)
        if "FROM bank_accounts" in teks:
            return self.rekening
        return self.mutasi


REKENING = [
    _Baris(
        id=1, bankName="BCA", bankAccountName="Operasional",
        bankAccountNumber="111", excludeFromCalendar=0,
    ),
    _Baris(
        id=2, bankName="Mandiri", bankAccountName="Jaminan",
        bankAccountNumber="222", excludeFromCalendar=1,
    ),
    _Baris(
        id=3, bankName="BNI", bankAccountName="Gaji",
        bankAccountNumber="333", excludeFromCalendar=0,
    ),
]

MUTASI = [
    _Baris(bankAccountID=1, balance=1_000_000, lastMutationDate=dt.date(2026, 9, 1)),
    _Baris(bankAccountID=2, balance=7_500_000, lastMutationDate=dt.date(2026, 9, 2)),
    _Baris(bankAccountID=3, balance=250_000, lastMutationDate=dt.date(2026, 9, 3)),
]


@pytest.fixture
def db(monkeypatch):
    t = _Db(MUTASI, REKENING)
    monkeypatch.setattr(modul, "database", t)
    return t


# ----------------------------------------------------------------------
# Tanpa daftar rekening — keadaan beranda
# ----------------------------------------------------------------------


async def test_total_tidak_memuat_rekening_dikecualikan(db):
    hasil = await DashboardModel.fetch_cash_position()

    assert hasil["totalBalance"] == 1_250_000, (
        "Total Saldo memuat rekening yang dikecualikan — beranda melaporkan "
        "kas yang lebih besar daripada uang yang benar dapat dipakai"
    )


async def test_rekening_dikecualikan_tetap_dilaporkan(db):
    """Dikeluarkan dari perhitungan, BUKAN dihilangkan dari daftar."""
    hasil = await DashboardModel.fetch_cash_position()

    idn = [a["bankAccountID"] for a in hasil["accounts"]]
    assert idn == [1, 2, 3], f"ada rekening yang hilang dari jawaban: {idn}"

    jaminan = next(a for a in hasil["accounts"] if a["bankAccountID"] == 2)
    assert jaminan["balance"] == 7_500_000, "saldonya ikut hilang"
    assert jaminan["excludeFromCalendar"] is True, (
        "barisnya tidak ditandai, sehingga layar tidak dapat menjelaskan "
        "kenapa penjumlahan barisnya tidak sama dengan totalnya"
    )


async def test_penjumlahannya_dapat_dicocokkan(db):
    """
    Angka yang tidak dapat dijumlahkan adalah angka yang dicurigai salah.

    Tanpa ketiga bilangan ini, rincian di layar memuat saldo yang tidak
    menjumlah menjadi angka mana pun yang dicetak kartunya.
    """
    hasil = await DashboardModel.fetch_cash_position()

    assert hasil["excludedBalance"] == 7_500_000
    assert hasil["excludedCount"] == 1
    assert hasil["grandTotalBalance"] == 8_750_000
    assert (
        hasil["totalBalance"] + hasil["excludedBalance"]
        == hasil["grandTotalBalance"]
    )
    assert sum(a["balance"] for a in hasil["accounts"]) == hasil["grandTotalBalance"]


async def test_kuerinya_membaca_kolom_tandanya(db):
    """
    Kolomnya harus DISEBUT di SELECT.

    Tanpa itu `getattr(baris, "excludeFromCalendar", False)` mengembalikan
    nilai bawaannya untuk SETIAP rekening — penyaringnya mati total, dan
    hasilnya identik dengan kode sebelum perbaikan ini. Tidak ada galat, tidak
    ada baris yang hilang; hanya totalnya yang kembali salah.
    """
    await DashboardModel.fetch_cash_position()

    sql_rekening = next(s for s in db.sql if "FROM bank_accounts" in s)
    assert "excludeFromCalendar" in sql_rekening, (
        "kueri rekening tidak membaca kolom tandanya"
    )


async def test_rekening_dikecualikan_tanpa_mutasi_tidak_menggeser_apa_pun(monkeypatch):
    """Rekening dikecualikan yang belum pernah bermutasi tetap nol di mana pun."""
    t = _Db([MUTASI[0]], REKENING)
    monkeypatch.setattr(modul, "database", t)

    hasil = await DashboardModel.fetch_cash_position()

    assert hasil["totalBalance"] == 1_000_000
    assert hasil["excludedBalance"] == 0
    assert hasil["excludedCount"] == 1


# ----------------------------------------------------------------------
# Dengan daftar rekening — keadaan proyeksi kas
# ----------------------------------------------------------------------


async def test_daftar_rekening_yang_disebut_menang_atas_tandanya(monkeypatch):
    """
    Tandanya adalah PILIHAN AWAL, bukan larangan.

    Pemilih rekening di kalender mencentangnya dengan `!excludeFromCalendar`,
    dan yang membukanya tetap boleh mencentang rekening jaminan. Bila tanda itu
    tetap menyaring sesudah rekeningnya diminta dengan nama, yang memintanya
    menerima NOL — dan proyeksi kas akan digambar dari titik jangkar yang
    salah, tanpa satu pun tanda bahwa angkanya bukan yang diminta.
    """
    t = _Db([MUTASI[1]], [REKENING[1]])
    monkeypatch.setattr(modul, "database", t)

    hasil = await DashboardModel.fetch_cash_position([2])

    assert hasil["totalBalance"] == 7_500_000, (
        "rekening yang diminta dengan nama tetap disaring oleh tandanya"
    )
    assert hasil["excludedBalance"] == 0
    assert hasil["excludedCount"] == 0
    assert hasil["accounts"][0]["excludeFromCalendar"] is False, (
        "ditandai dikecualikan padahal ikut dihitung — tandanya di jawaban "
        "harus berarti 'tidak masuk totalBalance', bukan sekadar menyalin "
        "kolomnya"
    )


async def test_proyeksi_kas_tidak_bergeser(monkeypatch):
    """
    `totalBalance` yang dibaca `proyeksi-kas` tidak berubah sama sekali.

    Ia SELALU mengirim daftar rekening, jadi perubahan ini tidak boleh
    menyentuh angkanya. Uji ini yang menjaga agar penamaan `totalBalance`
    tetap dapat dipercaya di sana.
    """
    t = _Db(MUTASI[:1] + MUTASI[2:], [REKENING[0], REKENING[2]])
    monkeypatch.setattr(modul, "database", t)

    hasil = await DashboardModel.fetch_cash_position([1, 3])

    assert hasil["totalBalance"] == 1_250_000
