"""Orkestrasi pencarian global (Ctrl+K)."""

from typing import Any, Dict, List

from repository.search_repository import SearchRepository
from utils.logger_utils import log_error
from utils.permission import is_allowed

BATAS_PER_KELOMPOK = 5
PANJANG_MINIMUM = 2


def _tgl(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


# (jenis, modul izin, pengambil, pembentuk baris)
#
# `jenis` dipetakan FE ke halaman tujuannya. Judul dan keterangan disusun DI
# SINI supaya FE tidak perlu tahu kolom mana milik tabel mana.
KELOMPOK = [
    ("proyek", "project", SearchRepository.proyek,
     lambda r: {"id": r["id"], "judul": f'{r["code"]} · {r["name"]}', "sub": None, "kunci": r["code"]}),
    ("klien", "client", SearchRepository.klien,
     lambda r: {"id": r["id"], "judul": " ".join(x for x in [r.get("prefix"), r["name"]] if x), "sub": r.get("city"), "kunci": r["name"]}),
    ("pemasok", "supplier", SearchRepository.pemasok,
     lambda r: {"id": r["id"], "judul": " ".join(x for x in [r.get("prefix"), r["name"]] if x), "sub": r.get("city"), "kunci": r["name"]}),
    ("purchase_order", "purchase_order", SearchRepository.purchase_order,
     lambda r: {"id": r["id"], "judul": r["name"], "sub": r.get("projectName"), "tanggal": _tgl(r.get("date")), "kunci": r["name"]}),
    ("pembelian", "purchase", SearchRepository.pembelian,
     lambda r: {"id": r["id"], "judul": r["invoiceName"], "sub": r.get("projectName"), "tanggal": _tgl(r.get("date")), "kunci": r["invoiceName"]}),
    ("faktur_penjualan", "sales_invoice", SearchRepository.faktur_penjualan,
     lambda r: {"id": r["id"], "judul": r["name"], "sub": r.get("projectName"), "tanggal": _tgl(r.get("date")), "kunci": r["name"]}),
    ("tender", "tender", SearchRepository.tender,
     lambda r: {"id": r["id"], "judul": " · ".join(x for x in [r.get("number"), r["name"]] if x), "sub": r.get("projectName"), "kunci": r["name"]}),
    ("karyawan", "employees", SearchRepository.karyawan,
     lambda r: {"id": r["id"], "judul": r["name"], "sub": r.get("position"), "kunci": r["name"]}),
]


class SearchController:
    @staticmethod
    async def cari(user: dict, q: str) -> Dict[str, Any]:
        """
        Hasil berkelompok, HANYA dari modul yang boleh dibaca pengguna.

        Izin diperiksa SEBELUM kueri, bukan hasilnya disaring sesudahnya:
        kelompok yang tidak berhak tidak pernah menyentuh basis data, dan
        tidak ada jalur kekeliruan yang membocorkan barisnya.

        Satu kelompok yang gagal dicatat dan dilewati — kotak pencarian yang
        kosong seluruhnya karena satu kolom yang hilang di satu tabel akan
        terbaca sebagai "tidak ada yang cocok", dan itu jawaban yang salah.
        """
        q = (q or "").strip()
        if len(q) < PANJANG_MINIMUM:
            return {"q": q, "kelompok": []}

        kelompok: List[Dict[str, Any]] = []
        for jenis, modul, ambil, bentuk in KELOMPOK:
            if not await is_allowed(user, modul, "read"):
                continue
            try:
                baris = await ambil(q, BATAS_PER_KELOMPOK)
            except Exception as e:  # noqa: BLE001
                log_error(f"Pencarian global {jenis} gagal: {e}")
                continue
            if baris:
                kelompok.append({"jenis": jenis, "hasil": [bentuk(r) for r in baris]})
        return {"q": q, "kelompok": kelompok}
