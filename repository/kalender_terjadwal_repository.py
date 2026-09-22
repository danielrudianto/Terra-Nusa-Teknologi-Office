"""
Pembayaran TERJADWAL dan TERTUNDA untuk saldo rencana kalender, proyeksi kas,
dan unduhan kalender — satu sumber supaya ketiganya berhenti berselisih.

MENGAPA PERLU

Saldo awal (bulan atau rentang) diambil dari view `mutation`, yang hanya
memuat pembayaran yang SUDAH DISETUJUI. Pembayaran yang masih menunggu
persetujuan tidak ada di sana. Akibatnya (22 Sep 2026, Oktober):

  * layar kalender Oktober mulai dari saldo awal Oktober — pembayaran
    September tanggal 24–30 yang belum disetujui (Rp 535 jt) HILANG,
    padahal kalender September menampilkannya: saldo 31 Okt 696 jt;
  * proyeksi kas hanya memakai rencana kas — seluruh pembayaran terjadwal
    (Rp 1,05 M) tidak ikut: 1,21 M;
  * unduhan rentang 21 Sep – 7 Nov (dan hitungan manual Daniel): 161 jt.

Aturan bersamanya:
  * `bawaan` — pembayaran BELUM disetujui (dan tidak ditolak/dihapus)
    bertanggal SEBELUM titik mulai. Uangnya belum bergerak, kewajibannya
    belum hilang; ia dibawa masuk ke saldo awal, seperti rencana yang
    belum jalan dari bulan sebelumnya.
  * `harian` — SELURUH pembayaran (disetujui atau belum, tidak dihapus)
    per tanggal di dalam rentang, untuk proyeksi.

Ditolak = `isDelete = 1` (lihat penyaring `isRejected` pada daftar
pembayaran), jadi cukup `isDelete = 0 AND isApprove = 0`.
"""

from datetime import date
from typing import Any, Dict, List, Optional

from utils.database import database

TABEL = (
    ("keluar", "payment_outgoing"),
    ("masuk", "payment_incoming"),
)


def _filter_rekening(ids: Optional[List[int]]) -> str:
    if not ids:
        return ""
    return " AND bankAccountID IN (" + ",".join(str(int(x)) for x in ids) + ")"


class KalenderTerjadwalRepository:
    @staticmethod
    async def bawaan(sebelum: date, rekening: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Per rekening: total keluar/masuk yang BELUM disetujui sebelum `sebelum`."""
        hasil: Dict[int, Dict[str, Any]] = {}
        for arah, tabel in TABEL:
            baris = await database.fetch_all(
                f"SELECT bankAccountID AS id, COALESCE(SUM(amount), 0) AS total, "
                f"COUNT(*) AS jumlah FROM {tabel} "
                f"WHERE isDelete = 0 AND isApprove = 0 AND date < :sebelum"
                f"{_filter_rekening(rekening)} GROUP BY bankAccountID",
                {"sebelum": sebelum},
            )
            for b in baris:
                d = hasil.setdefault(
                    int(b["id"]) if b["id"] is not None else 0,
                    {"bankAccountID": b["id"], "keluar": 0.0, "masuk": 0.0, "jumlah": 0},
                )
                d[arah] = round(d[arah] + float(b["total"] or 0), 2)
                d["jumlah"] += int(b["jumlah"] or 0)
        return list(hasil.values())

    @staticmethod
    async def harian(
        mulai: date, akhir: date, rekening: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """Per tanggal: total keluar/masuk SELURUH pembayaran tidak dihapus."""
        per: Dict[str, Dict[str, Any]] = {}
        for arah, tabel in TABEL:
            baris = await database.fetch_all(
                f"SELECT date AS tanggal, COALESCE(SUM(amount), 0) AS total FROM {tabel} "
                f"WHERE isDelete = 0 AND date >= :mulai AND date <= :akhir"
                f"{_filter_rekening(rekening)} GROUP BY date",
                {"mulai": mulai, "akhir": akhir},
            )
            for b in baris:
                t = b["tanggal"]
                k = t.isoformat() if hasattr(t, "isoformat") else str(t)[:10]
                d = per.setdefault(k, {"tanggal": k, "keluar": 0.0, "masuk": 0.0})
                d[arah] = round(d[arah] + float(b["total"] or 0), 2)
        return [per[k] for k in sorted(per)]
