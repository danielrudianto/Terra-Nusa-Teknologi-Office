"""
Pencarian GLOBAL (Ctrl+K) — satu kotak untuk klien, pemasok, karyawan,
PENGGUNA, proyek, tender, purchase order, pembelian, dan faktur penjualan.

Setiap kelompok adalah kueri kecil sendiri (maksimal `batas` baris), bukan
satu UNION besar: kelompok yang tidak boleh dilihat pengguna tidak pernah
dikueri sama sekali, dan satu tabel yang bermasalah tidak menjatuhkan
kelompok lain (lihat SearchController).

`contains(..., autoescape=True)` meloloskan `%` dan `_` dari ketikan
pengguna. Tanpa itu, mengetik "50%" berarti "50 diikuti apa saja", dan
garis bawah pada nomor dokumen cocok dengan karakter mana pun.
"""

from typing import Any, Dict, List

from sqlalchemy import or_, select

from models.client_model import clients_table
from models.employee_model import employees_table
from models.project_model import projects_table
from models.purchase_model import purchases_table
from models.purchase_order_model import purchase_orders_table
from models.sales_invoice_model import sales_invoice_tables
from models.supplier_model import suppliers_table
from models.user_model import users_table
from models.tender_model import tenders_table
from utils.database import database


def _cocok(q: str, *kolom):
    return or_(*[k.contains(q, autoescape=True) for k in kolom])


async def _ambil(kueri) -> List[Dict[str, Any]]:
    baris = await database.fetch_all(kueri)
    return [dict(b._mapping) if hasattr(b, "_mapping") else dict(b) for b in baris]


class SearchRepository:
    @staticmethod
    async def klien(q: str, batas: int):
        t = clients_table
        return await _ambil(
            select(t.c.id, t.c.prefix, t.c.name, t.c.city)
            .where(t.c.isDelete == False, _cocok(q, t.c.name, t.c.npwp, t.c.city))  # noqa: E712
            .order_by(t.c.name)
            .limit(batas)
        )

    @staticmethod
    async def pemasok(q: str, batas: int):
        t = suppliers_table
        return await _ambil(
            select(t.c.id, t.c.prefix, t.c.name, t.c.city)
            .where(t.c.isDelete == False, _cocok(q, t.c.name, t.c.npwp, t.c.city))  # noqa: E712
            .order_by(t.c.name)
            .limit(batas)
        )

    @staticmethod
    async def karyawan(q: str, batas: int):
        # Hanya NAMA yang dicari. NIK sengaja tidak: mengetik sebagian nomor
        # identitas lalu melihat nama siapa yang muncul adalah cara menebak
        # NIK orang lain.
        t = employees_table
        return await _ambil(
            select(t.c.id, t.c.name, t.c.position)
            .where(t.c.isDelete == False, _cocok(q, t.c.name))  # noqa: E712
            .order_by(t.c.name)
            .limit(batas)
        )

    @staticmethod
    async def pengguna(q: str, batas: int):
        """
        Pengguna aplikasi — BERBEDA dari karyawan.

        Keduanya orang, tetapi menjawab pertanyaan yang berbeda: karyawan
        adalah yang digaji, pengguna adalah yang punya akun. Tidak semua
        karyawan punya akun, dan sebagian akun bukan karyawan (konsultan dari
        luar, misalnya). Mencari "siapa yang punya akses" lewat daftar
        karyawan karena itu tidak pernah menemukan keduanya.

        Kelompok ini dijaga `user:read` — level 5 — dan di situlah surel boleh
        ikut dicari: yang berhak membukanya sudah dapat melihat seluruh daftar
        penggunanya. Berbeda dari NIK pada karyawan, yang sengaja tidak dapat
        dicari karena mengetik sebagian nomor lalu melihat nama siapa yang
        muncul adalah cara menebak nomor orang lain.

        Kolom penandanya `isDeleted`, BUKAN `isDelete` seperti tabel lain.
        """
        t = users_table
        return await _ambil(
            select(t.c.id, t.c.name, t.c.email, t.c.position, t.c.isActive)
            .where(
                t.c.isDeleted == False,  # noqa: E712
                _cocok(q, t.c.name, t.c.email),
            )
            .order_by(t.c.name)
            .limit(batas)
        )

    @staticmethod
    async def proyek(q: str, batas: int):
        t = projects_table
        return await _ambil(
            select(t.c.id, t.c.code, t.c.name)
            .where(t.c.isDelete == False, _cocok(q, t.c.code, t.c.name))  # noqa: E712
            .order_by(t.c.code)
            .limit(batas)
        )

    @staticmethod
    async def tender(q: str, batas: int):
        t = tenders_table
        return await _ambil(
            select(t.c.id, t.c.number, t.c.name, t.c.projectName)
            .where(t.c.isDelete == False, _cocok(q, t.c.number, t.c.name))  # noqa: E712
            .order_by(t.c.id.desc())
            .limit(batas)
        )

    @staticmethod
    async def purchase_order(q: str, batas: int):
        t = purchase_orders_table
        return await _ambil(
            select(t.c.id, t.c.name, t.c.projectName, t.c.date)
            .where(t.c.isDelete == False, _cocok(q, t.c.name, t.c.projectName))  # noqa: E712
            .order_by(t.c.id.desc())
            .limit(batas)
        )

    @staticmethod
    async def pembelian(q: str, batas: int):
        t = purchases_table
        return await _ambil(
            select(t.c.id, t.c.invoiceName, t.c.projectName, t.c.date)
            .where(
                t.c.isDelete == False,  # noqa: E712
                _cocok(q, t.c.invoiceName, t.c.purchaseOrderName),
            )
            .order_by(t.c.id.desc())
            .limit(batas)
        )

    @staticmethod
    async def faktur_penjualan(q: str, batas: int):
        t = sales_invoice_tables
        return await _ambil(
            select(t.c.id, t.c.name, t.c.projectName, t.c.date)
            .where(t.c.isDelete == False, _cocok(q, t.c.name, t.c.projectName))  # noqa: E712
            .order_by(t.c.id.desc())
            .limit(batas)
        )
