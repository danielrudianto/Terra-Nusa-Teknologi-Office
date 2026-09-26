"""
Perkakas untuk pengujian INTEGRASI — yang benar-benar memanggil endpoint.

Kenapa ini ada
--------------

Delapan puluh delapan berkas uji di folder ini memeriksa SUMBER: membaca
berkas controller, memotong badan fungsinya, lalu memastikan aturannya
tertulis di sana. Itu cepat, tidak butuh basis data, dan menangkap banyak hal.

Yang TIDAK ditangkapnya adalah kelas kegagalan yang paling sering terjadi di
sistem ini: endpoint yang menjawab bentuk yang salah, kueri yang menyaring
berbeda dari yang menghitung, kolom yang tidak sampai ke basis data, dan
tulisan yang gagal tanpa suara. Semuanya baru ketahuan ketika ada orang
menekan tombol.

Beberapa yang benar-benar terjadi:

  * `PUT /banks/{id}` tidak pernah berhasil sekali pun — muatannya membawa
    bidang yang bukan kolom tabel, dan galatnya ditelan `except Exception`.
  * `GET /banks` menerima `keyword` lalu mengabaikannya; kotak pencariannya
    tidak pernah berpengaruh.
  * Kueri penghitung halaman menyaring `isDelete`, kueri datanya tidak —
    paginator menyebut satu angka, tabelnya menampilkan angka lain.
  * `banks/all` dilayani dari cache Redis yang tidak pernah disegarkan.

Tidak satu pun tertangkap uji statis. Semuanya akan tertangkap di sini.

Cara menjalankan
----------------

Uji ini MENULIS ke basis data yang ditunjuk, jadi ia menolak berjalan sampai
basis datanya disebut dengan sengaja:

    TEST_DATABASE_URL="mysql://pengguna:sandi@localhost/tnt_restore_test" \\
        ./env/bin/python -m pytest test/integrasi_*_test.py -q

Tanpa variabel itu, seluruh berkas `integrasi_*_test.py` dilewati dan
`deploy.sh` tetap hijau seperti biasa.

Basis data ujinya paling mudah disiapkan dari cadangan:

    ./scripts/restore_db.sh cadangan-terbaru.sql.gz

Skrip itu memulihkan ke `<nama>_restore_test`, bukan ke yang asli. Dua
keuntungan sekaligus: strukturnya persis sama dengan produksi — termasuk view
`balance` dan `mutation` yang definisinya TIDAK ada di repo — dan cadangannya
ikut terbukti benar-benar bisa dipulihkan.

Bila Meilisearch tidak hidup
----------------------------

`utils/meilisearch.py` menyambung ke Meilisearch **pada saat modulnya
di-import**, bukan saat dipakai: baris 13 membuat kliennya, lalu modul itu
langsung memanggil `update_settings`, `update_synonyms`, dan
`update_typo_tolerance` di tingkat modul. Karena `controllers/` meng-import
klien itu, `routes/routes.py` — dan karenanya SELURUH aplikasi — tidak dapat
di-import sama sekali tanpa Meilisearch hidup.

Di server hal ini bukan masalah: Meilisearch berjalan di 127.0.0.1:7700. Di
mesin lain (laptop, kontainer CI) pintu darurat berikut mematikan panggilan
indeksnya, TANPA menyentuh kode produksi:

    TEST_TANPA_MEILI=1 TEST_DATABASE_URL="mysql://..." \\
        ./env/bin/python -m pytest test/integrasi_*_test.py -q

Yang digantikan hanya pustaka `meilisearch` itu sendiri, dan hanya di dalam
proses pengujian. Konsekuensinya jujur dan perlu diingat: dengan pintu ini
menyala, apa pun yang berhubungan dengan PENCARIAN tidak benar-benar diuji —
panggilan indeksnya masuk ke ruang hampa. Pakai untuk menguji yang lain, bukan
untuk menyatakan pencariannya sehat.

Yang dijaga di sini
-------------------

Setiap uji membereskan barisnya sendiri lewat `bersihkan`. Uji yang
meninggalkan sampah membuat uji berikutnya bergantung pada urutan, dan
kegagalan yang muncul belakangan tidak dapat dilacak ke penyebabnya.
"""

import os
import sys
import uuid
from datetime import date as d, datetime as dt

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")

#: Penanda untuk seluruh uji integrasi.
butuh_db = pytest.mark.skipif(
    not TEST_DB,
    reason=(
        "TEST_DATABASE_URL belum disetel. Uji integrasi memanggil endpoint "
        "sungguhan dan MENULIS ke basis datanya, jadi ia menolak berjalan "
        "sampai basis data ujinya ditunjuk dengan sengaja."
    ),
)


def _lewati_meilisearch() -> None:
    """
    Pintu darurat: matikan pustaka `meilisearch` sebelum aplikasinya di-import.

    Hanya aktif bila `TEST_TANPA_MEILI` disetel, dan hanya di dalam proses
    pengujian — kode produksi tidak disentuh sama sekali.

    Yang diganti adalah pustaka pihak ketiganya, bukan `utils/meilisearch.py`.
    Alasannya: ketiga modul indeks (`meilisearch`, `_item`, `_equipment`)
    berbagi satu klien yang dibuat di modul pertama, jadi menggantinya di satu
    tempat paling atas menutup ketiganya sekaligus. Mengganti modul `utils/`
    satu per satu berarti menulis ulang tiruan untuk tiap modul, dan tiruan itu
    akan diam-diam basi begitu modul aslinya berubah.

    Segala panggilan ke kliennya menjadi tanpa-akibat dan mengembalikan objek
    yang sama, sehingga rantai seperti `client.index(n).update_settings(s)`
    tetap sah.
    """
    if not os.environ.get("TEST_TANPA_MEILI"):
        return
    if "meilisearch" in sys.modules:
        return

    import types

    class _Hampa:
        """Menelan panggilan apa pun, mengembalikan dirinya sendiri."""

        def __call__(self, *a, **k):
            return self

        def __getattr__(self, _nama):
            return self

        def __iter__(self):
            return iter(())

        def __bool__(self):
            return True

    modul = types.ModuleType("meilisearch")
    modul.Client = _Hampa()  # type: ignore[attr-defined]
    modul.__terrabot_tiruan__ = True  # type: ignore[attr-defined]
    sys.modules["meilisearch"] = modul


def tanda() -> str:
    """
    Penanda unik untuk data yang dibuat satu uji.

    Dipakai pada nama dan nomor supaya barisnya selalu dapat ditemukan
    kembali untuk dibersihkan, dan tidak pernah bentrok dengan data sungguhan
    yang mungkin ada di basis data pulihan.
    """
    return f"UJI-{uuid.uuid4().hex[:10]}"


async def buat_aplikasi():
    """
    Aplikasi FastAPI berisi rute SUNGGUHAN, dengan pintu autentikasi diganti.

    Bukan `main.app`. Lifespan-nya menyambungkan Meilisearch dan Redis lalu
    menyinkronkan indeks — pekerjaan berat yang tidak ada hubungannya dengan
    apa pun yang diuji di sini, dan yang gagalnya akan menghentikan seluruh
    berkas hanya karena satu layanan pendukung sedang mati.

    Yang diambil adalah `routes/routes.py` — router yang sama persis dengan
    yang dipakai produksi, lengkap dengan prefix dan penjaga izinnya.
    """
    from fastapi import FastAPI

    _lewati_meilisearch()

    from routes.routes import router
    from utils.auth_utils import get_current_user
    from utils.database import database
    from models.user_model import users_table

    app = FastAPI()
    app.include_router(router)

    # Pengguna sungguhan dari basis data uji, bukan objek tiruan.
    #
    # `require()` memeriksa izin khusus dan wilayah divisi dengan MENGUERI
    # tabel memakai id pengguna ini. Objek tiruan membuat pemeriksaan izinnya
    # ikut palsu — dan izin adalah salah satu hal yang paling perlu diuji
    # sungguhan.
    pengguna = await database.fetch_one(
        users_table.select()
        .where(users_table.c.isActive == True)  # noqa: E712
        .where(users_table.c.isDeleted == False)  # noqa: E712
        .where(users_table.c.authenticationLevel == 5)
        .limit(1)
    )
    if pengguna is None:
        pytest.skip(
            "Basis data uji tidak punya pengguna aktif level 5; "
            "pengujian integrasi memerlukannya untuk melewati penjaga izin."
        )

    async def _pengguna_uji():
        return pengguna

    app.dependency_overrides[get_current_user] = _pengguna_uji
    return app, pengguna


@pytest.fixture
async def sambungan():
    """
    Sambungan basis data yang hidup DI DALAM event loop uji ini.

    Ini bukan kerapian, melainkan syarat. pytest-asyncio membuat event loop
    baru untuk setiap uji, sedangkan `database` adalah objek global yang
    dipakai bersama seluruh aplikasi. Kalau sambungannya dibiarkan menempel
    dari uji sebelumnya, kolam koneksinya masih terikat pada loop yang sudah
    ditutup, dan uji kedua gagal dengan "attached to a different loop" —
    kegagalan yang tampak seperti bug aplikasi padahal murni salah pasang.

    Karena itu: putuskan yang tersisa, sambungkan ulang, dan putuskan lagi di
    akhir. Semua fixture lain bergantung pada yang ini supaya sambungannya
    dibongkar PALING AKHIR — setelah `bersihkan` selesai menghapus barisnya.
    """
    from utils.database import database

    if database.is_connected:
        try:
            await database.disconnect()
        except Exception:  # noqa: BLE001
            # Sisa dari loop yang sudah mati; tidak ada yang perlu diselamatkan.
            pass

    await database.connect()
    try:
        yield database
    finally:
        try:
            await database.disconnect()
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture
async def klien(sambungan):
    """Klien HTTP yang menembak aplikasi sungguhan, tanpa server."""
    from httpx import ASGITransport, AsyncClient

    app, pengguna = await buat_aplikasi()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://uji"
    ) as c:
        c.pengguna = pengguna  # type: ignore[attr-defined]
        yield c


@pytest.fixture
async def bersihkan(sambungan):
    """
    Hapus baris yang dibuat uji, apa pun hasilnya.

    Dipakai:
        bersihkan(bank_accounts_table, id_baru)

    Penghapusannya KERAS (`delete`), bukan soft delete: yang dibersihkan
    adalah sampah pengujian, dan menyisakannya sebagai baris terhapus tetap
    membuatnya ikut terhitung pada kueri yang membaca semua keadaan.
    """
    dibuat: list[tuple] = []

    def daftar(tabel, id_baris):
        dibuat.append((tabel, id_baris))

    yield daftar

    from utils.database import database

    # Urutan dibalik: yang dibuat belakangan biasanya menunjuk yang lebih awal.
    for tabel, id_baris in reversed(dibuat):
        try:
            await database.execute(tabel.delete().where(tabel.c.id == id_baris))
        except Exception:  # noqa: BLE001
            # Kegagalan membersihkan tidak boleh menutupi hasil ujinya sendiri.
            pass
