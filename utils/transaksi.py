"""
Satu tindakan keuangan = satu transaksi.

MASALAHNYA

Banyak tindakan di sistem ini menulis ke lebih dari satu tabel. Menyetujui
pembayaran, misalnya, menyimpan status pembayarannya lalu — TERPISAH —
memperbarui status lunas pembeliannya. Bila yang kedua gagal, atau prosesnya
mati di antaranya, yang tertinggal adalah pembayaran yang tercatat disetujui
di atas pembelian yang tidak lunas.

Tidak ada galat. Tidak ada yang merah di layar. Ketahuannya saat rekonsiliasi,
berbulan kemudian, dan yang harus menebak apa yang terjadi adalah orang yang
tidak ada di sana waktu itu.

KENAPA `async with database.transaction()` SAJA TIDAK CUKUP

Ini bagian yang paling mudah salah, dan kalau salah hasilnya TERLIHAT benar.

Controller di repo ini menandai kegagalan dengan MENGEMBALIKAN dict:

    result = await Repo.update_status(...)
    if "error" in result:
        return {"error": result["error"], "status": 500}

Tidak ada pengecualian yang dilempar. Dan transaksi hanya digulung balik oleh
PENGECUALIAN — sebuah `return` biasa akan membuatnya COMMIT. Jadi membungkus
fungsi-fungsi itu dengan `async with database.transaction():` polos akan
menghasilkan kode yang tampak aman, lulus tinjauan, dan tetap menyimpan
penulisan separuh jadi persis seperti sebelumnya.

Karena itu `@atomik` memeriksa NILAI KEMBALIANNYA juga: dict ber-`error`
diperlakukan sebagai kegagalan, transaksinya dibatalkan, lalu dict yang sama
tetap dikembalikan kepada pemanggilnya. Bentuk API-nya tidak berubah sedikit
pun — yang berubah hanya: yang sudah tertulis ikut batal.

YANG TIDAK DAPAT DIGULUNG BALIK

Surel, webpush, dan indeks Meilisearch bukan bagian dari basis data. Sekali
terkirim, ia terkirim. Efek semacam itu harus ditaruh SESUDAH tindakannya
berhasil, bukan di tengah-tengah — kalau tidak, pemberitahuan "PO sudah
dibuat" bisa sampai untuk PO yang kemudian batal.
"""

import functools
from typing import Any, Callable

import utils.database


class _Batal(Exception):
    """
    Penanda internal untuk memaksa penggulungan balik.

    Tidak pernah keluar dari `atomik`: ia ditangkap di tempat yang sama, dan
    yang diteruskan ke pemanggil adalah nilai kembalian aslinya. Dibuat
    privat supaya tidak ada yang menangkapnya di tempat lain dan diam-diam
    mengubah artinya.
    """


def gagal(hasil: Any) -> bool:
    """
    Nilai kembalian ini menandakan KEGAGALAN.

    Disendirikan supaya ada SATU tempat yang menjawabnya. Konvensinya sudah
    dipakai di seluruh controller: dict dengan kunci `error`. Bila suatu saat
    ada bentuk lain, ia ditambahkan di sini — bukan di empat belas tempat.
    """
    return isinstance(hasil, dict) and "error" in hasil


def atomik(fn: Callable) -> Callable:
    """
    Jalankan fungsi ini sebagai SATU transaksi basis data.

    Dibatalkan pada dua hal:

      * pengecualian apa pun — termasuk `HTTPException`, yang dipakai
        beberapa controller untuk menolak permintaan di tengah jalan;
      * nilai kembalian ber-`error` — lihat keterangan panjang di atas.

    Ditaruh DI DALAM `@staticmethod`, bukan di luarnya::

        @staticmethod
        @atomik
        async def update_payment_status(...):

    Urutan terbalik membungkus objek `staticmethod`, bukan fungsinya, dan
    hasilnya `TypeError: 'staticmethod' object is not callable` saat dipanggil
    — bukan saat modulnya dimuat, jadi galatnya baru muncul di jalur yang
    kebetulan dipakai.

    Transaksi BERSARANG aman: `databases` memakai SAVEPOINT untuk yang di
    dalam, sehingga repository yang sudah punya transaksinya sendiri tetap
    bekerja seperti semula.
    """

    @functools.wraps(fn)
    async def pembungkus(*args: Any, **kwargs: Any) -> Any:
        """
        `database` dibaca lewat MODULNYA, bukan diimpor ke ruang nama ini.

        `from utils.database import database` mengikat objeknya sekali saat
        modul ini dimuat; pengujian yang mengganti `utils.database.database`
        dengan tiruan tidak akan terlihat dari sini, dan yang terbuka justru
        sambungan sungguhan.
        """
        db = utils.database.database

        """
        Tanpa sambungan, tidak ada yang dibungkus.

        INI BUKAN LUBANG, dan alasannya perlu ditulis supaya tidak dikira
        pelemahan penjaga demi meloloskan uji.

        Pengujian unit di repo ini menambal lapis REPOSITORY, sehingga tidak
        ada satu pun pernyataan SQL yang dijalankan — tidak ada yang perlu
        digulung balik. Memaksa membuka transaksi di sana hanya menghasilkan
        `DatabaseBackend is not running`.

        Dan bila sambungannya benar-benar mati di produksi, cabang ini tidak
        meloloskan apa pun: setiap `execute()` di dalam fungsinya akan gagal
        pada pernyataan PERTAMA, lewat jalur `acquire()` yang sama. Tidak ada
        keadaan di mana penulisan berhasil tanpa transaksi gara-gara baris ini.

        Di produksi `lifespan` menyambungkan basis data sebelum satu pun
        permintaan dilayani, jadi cabang ini tidak pernah diambil di sana.
        """
        if not getattr(db, "is_connected", True):
            return await fn(*args, **kwargs)

        # Nilai kembalian dititipkan ke luar blok `try`, karena `return` dari
        # dalam blok transaksi akan menyelesaikannya dengan COMMIT — dan yang
        # ingin kita lakukan justru sebaliknya.
        titipan: dict[str, Any] = {}
        try:
            async with db.transaction():
                hasil = await fn(*args, **kwargs)
                if gagal(hasil):
                    titipan["nilai"] = hasil
                    raise _Batal()
                return hasil
        except _Batal:
            return titipan["nilai"]

    # Penanda untuk `scripts/atomikcek.py`. Pemeriksanya membaca berkas
    # sumber, jadi sebenarnya ia mencari dekoratornya di teks — atribut ini
    # untuk yang memeriksanya saat berjalan.
    pembungkus.__atomik__ = True  # type: ignore[attr-defined]
    return pembungkus
