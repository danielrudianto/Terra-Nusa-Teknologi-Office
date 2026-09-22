"""
Tenggat beberapa hari ke depan untuk dasbor — "apa yang jatuh tempo minggu ini".

Satu daftar dari beberapa sumber, masing-masing DIJAGA IZINNYA SENDIRI (pola
yang sama dengan lencana dan papan antrean): sumber yang tidak boleh dibaca
pengguna tidak muncul sama sekali, bukan muncul sebagai nol.

Sumber:
  rencanaKeluar        payment_plans keluar, status `rencana`   payment_plan:read
  pembayaranTerjadwal  payment_outgoing belum disetujui         payment_outgoing:read
  hutangJatuhTempo     purchases belum lunas, menurut dueDate   purchase:read
  tenderTutup          tender `berjalan`, menurut dueDate       tender:read
  pajak                tanggal setor/lapor pajak masa           tax:read

Yang SUDAH LEWAT dan masih menggantung ikut (ditandai `lewat`): tenggat yang
terlewat justru yang paling perlu terlihat. Batas ke belakangnya 60 hari,
supaya satu rencana lama yang terlupakan tidak menarik seluruh riwayat.

KEGAGALAN DISEBUT, TIDAK DIJAWAB KOSONG: sumber yang gagal dicatat di `gagal`,
dan layar menyebutnya. Daftar kosong berarti "tidak ada tenggat", pernyataan
yang berbeda dari "tidak tahu".

Rupiah hutang pembelian SENGAJA tidak dijumlahkan di sini: nilai tagihan
pembelian dirakit dari beberapa kolom dengan aturannya sendiri, dan menyalin
aturan itu ke kueri kedua adalah tempat kedua yang harus sepakat. Yang
ditampilkan jumlah dokumennya.
"""

from calendar import monthrange
from datetime import date, timedelta
from typing import Any, Dict, List

from utils.database import database
from utils.logger_utils import log_error

#: Seberapa jauh ke belakang yang terlewat masih ditampilkan.
MUNDUR_HARI = 60


def _iso(v: Any) -> str:
    return v.isoformat() if hasattr(v, "isoformat") else str(v)[:10]


def tenggat_pajak(hari_ini: date, sampai: date) -> List[Dict[str, Any]]:
    """
    Tanggal setor & lapor pajak masa yang jatuh di [hari_ini, sampai].

    PMK 81/2024: PPh masa disetor paling lambat tanggal 15 bulan berikutnya;
    SPT Masa PPh dilaporkan paling lambat tanggal 20; PPN disetor dan SPT
    Masa PPN dilaporkan paling lambat akhir bulan berikutnya. Masa yang
    dimaksud = bulan SEBELUM bulan tenggatnya.

    Hanya pengingat tanggal — sistem tidak tahu apakah sudah disetor, jadi
    yang sudah lewat tidak ditampilkan (tidak ada yang bisa ditandai selesai).
    """
    hasil: List[Dict[str, Any]] = []
    # Bulan tenggat yang tersentuh jendela (paling banyak dua).
    bulan = {(hari_ini.year, hari_ini.month), (sampai.year, sampai.month)}
    for th, bl in sorted(bulan):
        masa_th, masa_bl = (th - 1, 12) if bl == 1 else (th, bl - 1)
        akhir = monthrange(th, bl)[1]
        for kode, tgl in (
            ("pphSetor", date(th, bl, 15)),
            ("pphLapor", date(th, bl, 20)),
            ("ppnSetorLapor", date(th, bl, akhir)),
        ):
            if hari_ini <= tgl <= sampai:
                hasil.append(
                    {
                        "jenis": "pajak",
                        "kode": kode,
                        "tanggal": tgl.isoformat(),
                        "masa": f"{masa_th:04d}-{masa_bl:02d}",
                        "lewat": False,
                    }
                )
    return hasil


class DashboardTenggatRepository:
    @staticmethod
    async def rencana_keluar(dari: date, sampai: date) -> List[Dict[str, Any]]:
        baris = await database.fetch_all(
            "SELECT date AS tanggal, COUNT(*) AS jumlah, COALESCE(SUM(amount),0) AS nilai "
            "FROM payment_plans "
            "WHERE isDelete = 0 AND planType = 'keluar' AND status = 'rencana' "
            "AND date >= :dari AND date <= :sampai GROUP BY date",
            {"dari": dari, "sampai": sampai},
        )
        return [
            {"tanggal": _iso(b["tanggal"]), "jumlah": int(b["jumlah"]), "nilai": float(b["nilai"] or 0)}
            for b in baris
        ]

    @staticmethod
    async def pembayaran_terjadwal(dari: date, sampai: date) -> List[Dict[str, Any]]:
        baris = await database.fetch_all(
            "SELECT DATE(date) AS tanggal, COUNT(*) AS jumlah, COALESCE(SUM(amount),0) AS nilai "
            "FROM payment_outgoing "
            "WHERE isDelete = 0 AND isApprove = 0 "
            "AND DATE(date) >= :dari AND DATE(date) <= :sampai GROUP BY DATE(date)",
            {"dari": dari, "sampai": sampai},
        )
        return [
            {"tanggal": _iso(b["tanggal"]), "jumlah": int(b["jumlah"]), "nilai": float(b["nilai"] or 0)}
            for b in baris
        ]

    @staticmethod
    async def hutang_jatuh_tempo(dari: date, sampai: date) -> List[Dict[str, Any]]:
        baris = await database.fetch_all(
            "SELECT dueDate AS tanggal, COUNT(*) AS jumlah FROM purchases "
            "WHERE isDelete = 0 AND isPaid = 0 AND dueDate IS NOT NULL "
            "AND dueDate >= :dari AND dueDate <= :sampai GROUP BY dueDate",
            {"dari": dari, "sampai": sampai},
        )
        return [{"tanggal": _iso(b["tanggal"]), "jumlah": int(b["jumlah"])} for b in baris]

    @staticmethod
    async def tender_tutup(dari: date, sampai: date) -> List[Dict[str, Any]]:
        baris = await database.fetch_all(
            "SELECT id, name, documentNumber, dueDate AS tanggal FROM tenders "
            "WHERE isDelete = 0 AND status = 'berjalan' AND dueDate IS NOT NULL "
            "AND dueDate >= :dari AND dueDate <= :sampai ORDER BY dueDate",
            {"dari": dari, "sampai": sampai},
        )
        return [
            {
                "tanggal": _iso(b["tanggal"]),
                "id": b["id"],
                "judul": b["documentNumber"] or b["name"],
                "jumlah": 1,
            }
            for b in baris
        ]


async def kumpulkan_tenggat(user: dict, hari: int = 7) -> Dict[str, Any]:
    """Seluruh tenggat yang boleh dilihat `user`, urut tanggal."""
    from utils.permission import is_allowed

    hari = max(1, min(31, int(hari or 7)))
    hari_ini = date.today()
    sampai = hari_ini + timedelta(days=hari)
    dari = hari_ini - timedelta(days=MUNDUR_HARI)

    item: List[Dict[str, Any]] = []
    gagal: List[str] = []

    sumber = (
        ("rencanaKeluar", "payment_plan", DashboardTenggatRepository.rencana_keluar),
        ("pembayaranTerjadwal", "payment_outgoing", DashboardTenggatRepository.pembayaran_terjadwal),
        ("hutangJatuhTempo", "purchase", DashboardTenggatRepository.hutang_jatuh_tempo),
        ("tenderTutup", "tender", DashboardTenggatRepository.tender_tutup),
    )
    for jenis, modul, ambil in sumber:
        if not await is_allowed(user, modul, "read"):
            continue
        try:
            for b in await ambil(dari, sampai):
                item.append({**b, "jenis": jenis, "lewat": b["tanggal"] < hari_ini.isoformat()})
        except Exception as e:  # noqa: BLE001
            log_error(f"Tenggat {jenis} gagal: {e}")
            gagal.append(jenis)

    if await is_allowed(user, "tax", "read"):
        item.extend(tenggat_pajak(hari_ini, sampai))

    item.sort(key=lambda x: (x["tanggal"], x["jenis"]))
    return {
        "hariIni": hari_ini.isoformat(),
        "sampai": sampai.isoformat(),
        "item": item,
        "gagal": gagal,
    }
