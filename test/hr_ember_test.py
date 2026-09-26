"""
Enam ember daftar pelamar: jumlahnya harus MASUK AKAL, bukan sekadar ada.

KENAPA PENGUJIAN INI ADA

Lencana angka di menu samping dipercaya begitu saja. Tidak ada yang
membuka enam layar lalu menghitung barisnya satu per satu untuk memeriksa
apakah "12" benar-benar dua belas — justru lencananya dipasang supaya tidak
perlu melakukan itu. Maka angka yang salah akan dipercaya berbulan-bulan.

Dua sifat yang dijaga, dan dua-duanya mudah rusak tanpa galat apa pun:

  1. LIMA EMBER SALING LEPAS. Satu pelamar hanya boleh berada di satu
     kelompok. Bila `submit` ikut memuat yang sudah diwawancarai, angkanya
     tidak pernah turun; yang melihatnya menyangka ada tumpukan pekerjaan
     yang sebenarnya sudah selesai.

  2. `terbit` = SELURUH yang aktif. Ia penyebutnya. Bila ia ikut menghitung
     yang dihapus, seluruh persentase yang dihitung darinya meleset.

CARA MENGUJINYA

Basis data SQLite di dalam memori, tabel dibuat dari model yang sama yang
dipakai produksi, lalu SETIAP kombinasi status x isDelete dimasukkan satu
baris. Syarat embernya dijalankan sebagai SQL sungguhan — bukan dicocokkan
sebagai teks.

Mencocokkan teks kueri akan lolos oleh salah ketik yang paling mahal:
`isDelete == True` yang tertulis `isDelete == False` tetap berupa
perbandingan yang sah, tetap muncul di teks kuerinya, dan tetap salah.
"""

from datetime import datetime as dt

import pytest
from sqlalchemy import create_engine, func, select

from models.hr_recruitment_model import hr_candidates_table, hr_tests_table
from models.user_model import users_table
from repository.hr_recruitment_repository import EMBER, _syarat_ember

WAKTU = dt(2026, 9, 1, 0, 0, 0)
KIRIM = dt(2026, 9, 1, 1, 0, 0)
KADALUARSA = dt(2026, 12, 31, 0, 0, 0)

#: Tangga status yang mungkin ada di kolomnya.
SEMUA_STATUS = (
    "baru",
    "mengerjakan",
    "selesai",
    "dinilai",
    "diwawancara",
    "diterima",
    "ditolak",
)

#: Ember yang HARUS saling lepas — semuanya kecuali `terbit`, yang memang
#: penyebut, dan `dihapus`, yang hidup di sisi lain `isDelete`.
LEPAS = ("submit", "wawancara", "diterima", "ditolak")


@pytest.fixture()
def mesin():
    """SQLite di memori berisi setiap kombinasi status x isDelete."""
    e = create_engine("sqlite://")
    for t in (users_table, hr_tests_table, hr_candidates_table):
        t.create(e, checkfirst=True)

    baris = []
    i = 0
    for hapus in (0, 1):
        for st in SEMUA_STATUS:
            # `submittedAt` diisi untuk status yang memang sudah mengirim.
            # Ia ikut menentukan ember `submit`, dan membiarkannya kosong
            # untuk semua baris akan membuat ember itu selalu nol —
            # pengujian yang selalu hijau karena tidak ada yang diuji.
            sudah = st in ("selesai", "dinilai", "diwawancara", "diterima", "ditolak")
            i += 1
            baris.append(
                {
                    "id": i,
                    "testID": 1,
                    "name": f"Pelamar {i}",
                    "token": f"token-{i}",
                    "expiresAt": KADALUARSA,
                    "startedAt": WAKTU if st != "baru" else None,
                    "submittedAt": KIRIM if sudah else None,
                    "status": st,
                    "isDelete": hapus,
                    "createdAt": WAKTU,
                    "createdBy": 1,
                }
            )

    with e.begin() as c:
        c.execute(hr_candidates_table.insert(), baris)
    return e


def _id_ember(mesin, nama: str) -> set:
    syarat = _syarat_ember(nama)
    assert syarat is not None, nama
    q = select(hr_candidates_table.c.id).where(*syarat)
    with mesin.connect() as c:
        return {r[0] for r in c.execute(q)}


def test_nama_ember_tak_dikenal_ditolak():
    assert _syarat_ember("tidak-ada") is None
    assert _syarat_ember("") is None


def test_setiap_ember_punya_syarat():
    for nama in EMBER:
        assert _syarat_ember(nama) is not None, nama


def test_terbit_adalah_seluruh_yang_aktif(mesin):
    with mesin.connect() as c:
        aktif = c.execute(
            select(func.count()).where(hr_candidates_table.c.isDelete == 0)
        ).scalar()
    assert len(_id_ember(mesin, "terbit")) == aktif == len(SEMUA_STATUS)


def test_terbit_tidak_memuat_yang_dihapus(mesin):
    assert not (_id_ember(mesin, "terbit") & _id_ember(mesin, "dihapus"))


def test_dihapus_hanya_yang_dihapus(mesin):
    ids = _id_ember(mesin, "dihapus")
    assert len(ids) == len(SEMUA_STATUS)
    with mesin.connect() as c:
        for i in ids:
            assert c.execute(
                select(hr_candidates_table.c.isDelete).where(
                    hr_candidates_table.c.id == i
                )
            ).scalar() == 1


@pytest.mark.parametrize("a", LEPAS)
@pytest.mark.parametrize("b", LEPAS)
def test_ember_saling_lepas(mesin, a, b):
    if a == b:
        return
    tindih = _id_ember(mesin, a) & _id_ember(mesin, b)
    assert not tindih, f"{a} dan {b} berbagi baris {sorted(tindih)}"


def test_submit_berhenti_sebelum_keputusan(mesin):
    """`submit` = sudah mengirim, BELUM diputuskan."""
    ids = _id_ember(mesin, "submit")
    with mesin.connect() as c:
        status = {
            c.execute(
                select(hr_candidates_table.c.status).where(
                    hr_candidates_table.c.id == i
                )
            ).scalar()
            for i in ids
        }
    assert status == {"selesai", "dinilai"}


def test_submit_menuntut_submittedAt(mesin):
    """
    Status `selesai` dengan `submittedAt` kosong TIDAK dihitung mengirim.

    Baris seperti itu memang tidak seharusnya ada, tetapi pernah ada —
    status disetel tanpa waktunya. Yang menghitung antrean pekerjaan lebih
    baik melewatkan baris rusak daripada memasukkannya diam-diam.
    """
    with mesin.begin() as c:
        c.execute(
            hr_candidates_table.insert().values(
                id=900,
                testID=1,
                name="Tanpa waktu kirim",
                token="token-900",
                expiresAt=KADALUARSA,
                submittedAt=None,
                status="selesai",
                isDelete=0,
                createdAt=WAKTU,
                createdBy=1,
            )
        )
    assert 900 not in _id_ember(mesin, "submit")
    assert 900 in _id_ember(mesin, "terbit")


def test_lima_ember_menutupi_seluruh_yang_aktif_tanpa_sisa_ganda(mesin):
    """
    Jumlah kelima ember lepas + yang belum mengirim = jumlah `terbit`.

    Ini yang sebenarnya dilakukan orang dengan lencana: menjumlahkannya.
    """
    lepas = [_id_ember(mesin, n) for n in LEPAS]
    gabung = set().union(*lepas)
    assert sum(len(x) for x in lepas) == len(gabung)

    belum = _id_ember(mesin, "terbit") - gabung
    with mesin.connect() as c:
        status = {
            c.execute(
                select(hr_candidates_table.c.status).where(
                    hr_candidates_table.c.id == i
                )
            ).scalar()
            for i in belum
        }
    assert status == {"baru", "mengerjakan"}


# ---------------------------------------------------------------------
# Pencarian dan ringkasan — diperiksa lewat pernyataan yang benar-benar
# dikirim, bukan lewat teksnya.
# ---------------------------------------------------------------------

MODUL = "repository.hr_recruitment_repository"


def _kueri_baca(db):
    """Pernyataan SELECT terakhir yang dikirim ke basis data."""
    for m, q in reversed(db.calls):
        if m in ("fetch_all", "fetch_one"):
            return q
    return None


@pytest.mark.asyncio
async def test_pencarian_melarikan_persen_dan_garis_bawah(fake_db):
    """
    `%` dan `_` yang diketik pemakai adalah AKSARA, bukan pola.

    Tanpa pelarian, mencari "_" mencocokkan aksara apa pun: yang mengetik
    nomor telepon bergaris bawah mendapat seluruh daftar, dan tidak ada
    satu pun tanda bahwa pencariannya tidak dijalankan.
    """
    from repository.hr_recruitment_repository import HrRecruitmentRepository

    db = fake_db(MODUL)
    db.queue("fetch_all", [])

    await HrRecruitmentRepository.daftar_pelamar(cari="100%_naik")

    q = _kueri_baca(db)
    assert q is not None, "kueri tidak pernah dikirim"
    nilai = [v for v in q.compile().params.values() if isinstance(v, str)]
    pola = [v for v in nilai if v.startswith("%") and v.endswith("%")]
    assert pola, f"pola LIKE tidak terbentuk: {nilai}"
    for p in pola:
        assert "100\\%\\_naik" in p, p


@pytest.mark.asyncio
async def test_ember_tak_dikenal_ditolak_bukan_diabaikan(fake_db):
    """
    Nama ember yang salah ketik harus BERSUARA.

    Mengabaikannya diam-diam mengembalikan seluruh daftar, dan yang
    membukanya menyangka kelompoknya memang sebesar itu.
    """
    from repository.hr_recruitment_repository import HrRecruitmentRepository

    db = fake_db(MODUL)
    hasil = await HrRecruitmentRepository.daftar_pelamar(ember="terbitt")

    assert isinstance(hasil, dict) and hasil.get("status") == 400
    assert db.executed("fetch_all") == 0, "basis data tetap ditanyai"


@pytest.mark.asyncio
async def test_ringkasan_hanya_SATU_pertanyaan(fake_db):
    """
    Enam hitungan, satu pembacaan.

    Enam pembacaan terpisah berarti enam saat yang berbeda: pelamar yang
    statusnya berubah di antaranya terhitung dua kali, atau tidak sama
    sekali — dan selisih itu tidak pernah menimbulkan galat.
    """
    from repository.hr_recruitment_repository import HrRecruitmentRepository

    db = fake_db(MODUL)
    db.queue("fetch_one", {n: 1 for n in EMBER})

    hasil = await HrRecruitmentRepository.ringkasan_pelamar()

    assert set(hasil) == set(EMBER)
    assert db.executed("fetch_one") == 1
    assert db.executed("fetch_val") == 0
    assert db.executed("fetch_all") == 0
