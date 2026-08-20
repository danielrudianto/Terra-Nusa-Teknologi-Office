"""
Database tiruan untuk menguji repository tanpa server MySQL.

Repository memanggil `database.fetch_all / fetch_one / fetch_val / execute`.
Kelas di bawah menggantikan objek itu: nilai balikannya diantre lebih dulu
oleh pengujian, dan setiap kueri yang lewat ikut dicatat sehingga bisa
diperiksa (mis. memastikan sebuah kueri benar-benar dijalankan).

Dengan begini yang diuji adalah *perilaku* repository — bentuk balikan,
penanganan galat, urutan pemanggilan — bukan mesin basis datanya.
"""

from typing import Any, List


class FakeDatabase:
    def __init__(self) -> None:
        # nilai balikan yang diantre per metode
        self._queue: dict[str, List[Any]] = {
            "fetch_all": [],
            "fetch_one": [],
            "fetch_val": [],
            "execute": [],
        }
        # galat yang sengaja dilemparkan pada pemanggilan berikutnya
        self._raise: dict[str, Any] = {}
        # riwayat kueri yang dijalankan
        self.calls: List[tuple] = []
        # Nilai terikat tiap pemanggilan, sejajar dengan `calls`.
        self.calls_values: List[tuple] = []

    # ---- pengaturan dari sisi pengujian --------------------------------
    def queue(self, method: str, *values: Any) -> "FakeDatabase":
        """Antrekan nilai balikan; dipakai berurutan tiap pemanggilan."""
        self._queue[method].extend(values)
        return self

    def fail(self, method: str, error: Exception) -> "FakeDatabase":
        """Buat pemanggilan berikutnya melempar galat."""
        self._raise[method] = error
        return self

    def executed(self, method: str) -> int:
        return sum(1 for m, _ in self.calls if m == method)

    def last_query(self, method: str | None = None):
        for m, q in reversed(self.calls):
            if method is None or m == method:
                return q
        return None

    # ---- antarmuka yang dipakai repository -----------------------------
    #
    # `values` IKUT diterima dan dicatat.
    #
    # `databases` menerima kueri berupa teks beserta nilai terikatnya —
    # `fetch_all(sql, {"proyek": ...})` — dan repository yang menulis SQL
    # mentah memakai bentuk itu. Tanpa parameter ini, memanggilnya dari
    # pengujian gagal dengan "takes 2 positional arguments but 3 were given",
    # dan galatnya tertelan `except` di dalam repository sehingga yang
    # terlihat hanya hasil kosong tanpa sebab.
    async def _take(self, method: str, query: Any, default: Any, values: Any = None):
        # `calls` TETAP berpasangan dua.
        #
        # Belasan pengujian membongkarnya sebagai `for m, q in db.calls`;
        # menambahkan unsur ketiga mematahkan semuanya sekaligus — dan yang
        # gagal bukan hal yang sedang diubah, sehingga sebabnya sulit dikenali
        # oleh yang membaca hasilnya.
        #
        # Nilai terikat disimpan sejajar, dibaca lewat `last_values()`.
        self.calls.append((method, query))
        self.calls_values.append((method, values))
        if method in self._raise:
            raise self._raise.pop(method)
        queue = self._queue[method]
        return queue.pop(0) if queue else default

    async def fetch_all(self, query: Any, values: Any = None):
        return await self._take("fetch_all", query, [], values)

    async def fetch_one(self, query: Any, values: Any = None):
        return await self._take("fetch_one", query, None, values)

    async def fetch_val(self, query: Any, values: Any = None):
        return await self._take("fetch_val", query, None, values)

    async def execute(self, query: Any, values: Any = None):
        return await self._take("execute", query, 1, values)

    def last_values(self, method: str | None = None):
        """Nilai terikat pada pemanggilan terakhir; untuk memeriksa filternya."""
        for m, v in reversed(self.calls_values):
            if method is None or m == method:
                return v
        return None

    def transaction(self):
        """
        Transaksi tiruan.

        `databases` menyediakannya sebagai pengelola konteks asinkron, dan
        repository memakainya untuk menjaga beberapa pernyataan jadi-atau-batal
        bersama. Yang ditiru di sini hanya BENTUKNYA — tidak ada yang
        digulung balik, karena tidak ada basis data yang menyimpan apa pun.

        Pemanggilannya tetap dicatat, sehingga pengujian dapat memastikan
        sebuah repository memang membungkus pekerjaannya dalam transaksi.
        """
        self.calls.append(("transaction", None))

        class _Transaksi:
            async def __aenter__(_self):
                return _self

            async def __aexit__(_self, *_):
                return False

        return _Transaksi()
