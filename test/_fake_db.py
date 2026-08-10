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
    async def _take(self, method: str, query: Any, default: Any):
        self.calls.append((method, query))
        if method in self._raise:
            raise self._raise.pop(method)
        queue = self._queue[method]
        return queue.pop(0) if queue else default

    async def fetch_all(self, query: Any):
        return await self._take("fetch_all", query, [])

    async def fetch_one(self, query: Any):
        return await self._take("fetch_one", query, None)

    async def fetch_val(self, query: Any):
        return await self._take("fetch_val", query, None)

    async def execute(self, query: Any):
        return await self._take("execute", query, 1)
