"""
Rekening bank, lewat endpoint sungguhan.

Setiap uji di berkas ini menutup satu kegagalan yang BENAR-BENAR terjadi dan
lolos dari 88 berkas uji statis, karena semuanya baru terlihat ketika kueri
sungguhan dijalankan terhadap basis data sungguhan:

  * `PUT /banks/{id}` tidak pernah berhasil sekali pun.
  * `keyword` diterima lalu diabaikan.
  * penghitung halaman menyaring berbeda dari kueri datanya.
  * kolom pengurut dihitung lalu dibuang.
  * `banks/all` dilayani dari cache yang tidak pernah disegarkan.

Lihat `test/_integrasi.py` untuk cara menjalankannya.
"""

import pytest

from _integrasi import (  # noqa: F401
    butuh_db,
    sambungan,
    klien,
    bersihkan,
    tanda,
)

pytestmark = butuh_db


async def _buat_rekening(klien, bersihkan, nama_akun: str, nomor: str) -> int:
    from models.bank_model import bank_accounts_table

    r = await klien.post(
        "/banks/",
        json={
            "bankName": "Bank Uji",
            "bankAccountName": nama_akun,
            "bankAccountNumber": nomor,
        },
    )
    assert r.status_code == 200, r.text
    bank_id = r.json()["bank_id"]
    bersihkan(bank_accounts_table, bank_id)
    return bank_id


# ----------------------------------------------------------------------
# Menulis
# ----------------------------------------------------------------------

async def test_menyunting_rekening_berhasil(klien, bersihkan):
    """
    Ini yang dulu tidak pernah berhasil sekali pun.

    Rutenya mengirim `BankAccount.model_dump()`, dan model Pydantic itu memuat
    `balance` — bidang turunan yang BUKAN kolom tabel. SQLAlchemy menolak
    dengan "Unconsumed column names: balance", `except Exception` menelannya,
    dan yang sampai ke pemakai hanya "Terjadi kesalahan pada sistem".

    Tidak ada uji statis yang bisa menangkapnya: kodenya terbaca masuk akal
    baris demi baris. Yang membongkarnya hanya menjalankan kuerinya.
    """
    t = tanda()
    bank_id = await _buat_rekening(klien, bersihkan, f"Operasional {t}", t)

    r = await klien.put(
        f"/banks/{bank_id}",
        json={
            "id": bank_id,
            "bankName": "Bank Uji",
            "bankAccountName": f"Operasional {t} (diubah)",
            "bankAccountNumber": t,
            "excludeFromCalendar": True,
        },
    )
    assert r.status_code == 200, r.text

    r = await klien.get(f"/banks/{bank_id}")
    assert r.status_code == 200
    assert r.json()["bankAccountName"].endswith("(diubah)")
    assert r.json()["excludeFromCalendar"] is True


async def test_kolom_pembuatan_tidak_tertimpa_saat_disunting(klien, bersihkan):
    """
    `BankAccount.__init__` mengisi `createdAt` dengan waktu sekarang bila
    kosong, dan rutenya meneruskan `createdBy` apa adanya dari klien. Tanpa
    saringan, penyuntingan pertama yang berhasil menimpa tanggal pembuatan
    dan menghapus pencatat aslinya — justru jejak yang audit log dibuat untuk
    menjaganya.
    """
    from utils.database import database
    from models.bank_model import bank_accounts_table

    t = tanda()
    bank_id = await _buat_rekening(klien, bersihkan, f"Deposit {t}", t)

    sebelum = await database.fetch_one(
        bank_accounts_table.select().where(bank_accounts_table.c.id == bank_id)
    )

    r = await klien.put(
        f"/banks/{bank_id}",
        json={
            "id": bank_id,
            "bankName": "Bank Uji",
            "bankAccountName": f"Deposit {t} (diubah)",
            "bankAccountNumber": t,
        },
    )
    assert r.status_code == 200, r.text

    sesudah = await database.fetch_one(
        bank_accounts_table.select().where(bank_accounts_table.c.id == bank_id)
    )
    assert sesudah["createdAt"] == sebelum["createdAt"]
    assert sesudah["createdBy"] == sebelum["createdBy"]


# ----------------------------------------------------------------------
# Membaca — pencarian, pengurutan, hitungan
# ----------------------------------------------------------------------

async def test_pencarian_benar_benar_menyaring(klien, bersihkan):
    """`keyword` dulu diterima lalu tidak pernah dipakai."""
    t = tanda()
    await _buat_rekening(klien, bersihkan, f"Cari {t}", t)
    await _buat_rekening(klien, bersihkan, "Jangan ikut", tanda())

    r = await klien.get("/banks/", params={"page": 1, "keyword": t})
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    assert len(data) >= 1
    assert all(t in (b["bankAccountNumber"] + b["bankAccountName"]) for b in data)


async def test_pencarian_mencakup_nomor_maupun_nama(klien, bersihkan):
    """
    Yang mengetik di kotak pencarian tidak tahu kolom mana yang dicari.
    Mencari hanya pada satu kolom membuatnya tampak rusak justru ketika kata
    kuncinya benar.
    """
    t = tanda()
    await _buat_rekening(klien, bersihkan, f"Namanya {t}", tanda())

    r = await klien.get("/banks/", params={"page": 1, "keyword": t})
    assert r.status_code == 200
    assert any(t in b["bankAccountName"] for b in r.json()["data"])


async def test_hitungan_halaman_cocok_dengan_isinya(klien, bersihkan):
    """
    Kueri penghitung dulu menyaring `isDelete`, kueri datanya tidak.
    Paginator menyebut satu angka, tabelnya menampilkan angka lain — dan
    rekening yang sudah dihapus tetap muncul.
    """
    t = tanda()
    a = await _buat_rekening(klien, bersihkan, f"Aktif {t}", f"{t}-1")
    b = await _buat_rekening(klien, bersihkan, f"Hapus {t}", f"{t}-2")

    r = await klien.delete(f"/banks/{b}")
    assert r.status_code == 200, r.text

    r = await klien.get("/banks/", params={"page": 1, "keyword": t})
    assert r.status_code == 200
    hasil = r.json()

    # Bawaannya "aktif": yang terhapus tidak ikut, DAN tidak ikut dihitung.
    assert hasil["count"] == len(hasil["data"])
    assert [x["id"] for x in hasil["data"]] == [a]


async def test_keadaan_dihapus_dan_semua(klien, bersihkan):
    t = tanda()
    a = await _buat_rekening(klien, bersihkan, f"Aktif {t}", f"{t}-1")
    b = await _buat_rekening(klien, bersihkan, f"Hapus {t}", f"{t}-2")
    assert (await klien.delete(f"/banks/{b}")).status_code == 200

    r = await klien.get(
        "/banks/", params={"page": 1, "keyword": t, "keadaan": "dihapus"}
    )
    assert [x["id"] for x in r.json()["data"]] == [b]

    r = await klien.get(
        "/banks/", params={"page": 1, "keyword": t, "keadaan": "semua"}
    )
    assert sorted(x["id"] for x in r.json()["data"]) == sorted([a, b])


async def test_keadaan_yang_tidak_dikenal_jatuh_ke_aktif(klien, bersihkan):
    """
    Salah ketik pada parameter tidak boleh berakibat menampilkan rekening
    terhapus kepada yang tidak memintanya.
    """
    t = tanda()
    a = await _buat_rekening(klien, bersihkan, f"Aktif {t}", f"{t}-1")
    b = await _buat_rekening(klien, bersihkan, f"Hapus {t}", f"{t}-2")
    assert (await klien.delete(f"/banks/{b}")).status_code == 200

    r = await klien.get(
        "/banks/", params={"page": 1, "keyword": t, "keadaan": "ngawur"}
    )
    assert [x["id"] for x in r.json()["data"]] == [a]


async def test_pengurutan_benar_benar_berpengaruh(klien, bersihkan):
    """Kolom pengurut dulu dihitung ke dalam `_urut` lalu diabaikan."""
    t = tanda()
    await _buat_rekening(klien, bersihkan, f"Zulu {t}", f"{t}-1")
    await _buat_rekening(klien, bersihkan, f"Alfa {t}", f"{t}-2")

    naik = await klien.get(
        "/banks/",
        params={"page": 1, "keyword": t, "sortBy": "bankAccountName",
                "sortByDirection": "asc"},
    )
    turun = await klien.get(
        "/banks/",
        params={"page": 1, "keyword": t, "sortBy": "bankAccountName",
                "sortByDirection": "desc"},
    )

    nama_naik = [x["bankAccountName"] for x in naik.json()["data"]]
    nama_turun = [x["bankAccountName"] for x in turun.json()["data"]]
    assert nama_naik == sorted(nama_naik)
    assert nama_turun == list(reversed(nama_naik))


# ----------------------------------------------------------------------
# banks/all — sumbernya basis data, bukan cache
# ----------------------------------------------------------------------

async def test_banks_all_menampilkan_perubahan_terbaru(klien, bersihkan):
    """
    Dulu dilayani dari cache Redis yang ditulis SEKALI saat rekening dibuat
    dan tidak pernah disegarkan. Akibatnya ganti nama rekening tidak pernah
    muncul di dropdown mana pun, dan kolom baru tidak pernah sampai.

    Uji ini menyunting lalu membaca ulang; kalau cachenya kembali dipakai
    sebagai sumber, nama barunya tidak akan muncul di sini.
    """
    t = tanda()
    bank_id = await _buat_rekening(klien, bersihkan, f"Sebelum {t}", t)

    assert (
        await klien.put(
            f"/banks/{bank_id}",
            json={
                "id": bank_id,
                "bankName": "Bank Uji",
                "bankAccountName": f"Sesudah {t}",
                "bankAccountNumber": t,
                "excludeFromCalendar": True,
            },
        )
    ).status_code == 200

    r = await klien.get("/banks/all")
    assert r.status_code == 200
    baris = [x for x in r.json() if x["id"] == bank_id]
    assert baris, "rekening tidak muncul di banks/all"
    assert baris[0]["bankAccountName"] == f"Sesudah {t}"
    assert baris[0]["excludeFromCalendar"] is True


# ----------------------------------------------------------------------
# Penjaga saldo
# ----------------------------------------------------------------------

async def test_rekening_kosong_boleh_dihapus(klien, bersihkan):
    """
    Penjaga saldo tidak boleh kebablasan: rekening yang memang belum pernah
    dipakai harus tetap dapat dihapus. Bila `balance` tidak punya barisnya
    sama sekali, itu berarti nol — bukan "tidak diketahui".
    """
    t = tanda()
    bank_id = await _buat_rekening(klien, bersihkan, f"Kosong {t}", t)

    r = await klien.delete(f"/banks/{bank_id}")
    assert r.status_code == 200, r.text
