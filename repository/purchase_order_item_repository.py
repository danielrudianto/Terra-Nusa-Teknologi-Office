from typing import List
from sqlalchemy import insert, select, delete
from utils.database import database
from utils.logger_utils import log_error
from models.purchase_order_item_model import purchase_order_items_table
from models.master_item_model import master_item_table
from models.master_equipment_model import master_equipment_table

_COLUMNS = [
    "item_id", "equipment_id", "fleet_id", "task", "quantity", "price", "amount",
    "remarks_1", "remarks_2", "remarks_3", "remarks_4",
    "remarks_5", "remarks_6", "unit",
]


#: Selisih terbesar yang masih dianggap pembulatan, dalam rupiah.
#:
#: Sama dengan `TOLERANSI_PEMBULATAN` di layar. Dua angka yang berbeda di dua
#: tempat membuat baris yang diterima formulir ditolak server — atau yang
#: lebih buruk, sebaliknya.
TOLERANSI_PEMBULATAN = 5


def nilai_baris(item: dict) -> float:
    """Jumlah yang ditulis bila ada; selain itu volume kali harga."""
    ditulis = item.get("amount")
    if ditulis is None or ditulis == "":
        return float(item.get("quantity") or 0) * float(item.get("price") or 0)
    return float(ditulis)


def pembulatan_sah(item: dict) -> bool:
    """
    Jumlah yang ditulis masih dalam batas pembulatan.

    Diperiksa DI SINI, bukan cukup di formulir: muatan permintaan dapat
    disusun sendiri oleh siapa pun yang membuka Network tab, dan kolom ini
    menentukan angka yang tercetak pada dokumen yang mengikat vendor.
    """
    ditulis = item.get("amount")
    if ditulis is None or ditulis == "":
        return True
    try:
        selisih = abs(
            float(ditulis)
            - float(item.get("quantity") or 0) * float(item.get("price") or 0)
        )
    except (TypeError, ValueError):
        return False
    return selisih <= TOLERANSI_PEMBULATAN


def _clean_item(item: dict, po_id: int) -> dict:
    row = {"purchaseOrderID": po_id}
    # item_id  = barang katalog (master_item), dipakai PO G/F/C/5.1.x/6.3
    # equipment_id = alat sewa (master_equipment), dipakai PO B
    # Keduanya kolom terpisah dan tidak boleh saling menimpa.
    item = dict(item)
    for c in _COLUMNS:
        row[c] = item.get(c)
    # NOT NULL columns with sensible fallbacks
    row["quantity"] = row.get("quantity") or 0
    row["price"] = row.get("price") or 0
    row["unit"] = row.get("unit") or ""

    # Jumlah tertulis di luar batas pembulatan DIBUANG, bukan disimpan.
    #
    # Membuangnya membuat barisnya jatuh ke perkalian biasa — angka yang
    # selalu dapat dipertanggungjawabkan. Menyimpannya berarti dokumen
    # menyatakan nilai yang tidak dapat dicocokkan dengan volume dan
    # harganya, dan itu baru ketahuan di tangan vendor.
    if not pembulatan_sah(row):
        row["amount"] = None

    """
    `task` tidak disimpan untuk barang katalog.

    Namanya sudah ada pada master_item dan diambil lewat join saat dibaca.
    Menyalinnya ke sini berarti dokumen menyimpan nama yang dapat berbeda
    dari katalognya bila katalog itu diperbaiki — dan nama barang bahan
    bakar saja sudah melampaui 100 karakter, sehingga penyimpanannya gagal
    dengan galat "Data too long".

    Untuk baris yang TIDAK merujuk katalog — pekerjaan yang diketik bebas
    pada PO jasa — `task` tetap disimpan, dan dipotong pada batas kolomnya
    agar satu isian panjang tidak menggagalkan seluruh dokumen.
    """
    if row.get("item_id"):
        row["task"] = None
    elif row.get("task"):
        row["task"] = str(row["task"])[:100]

    return row


class PurchaseOrderItemRepository:
    @staticmethod
    async def insert_many(po_id: int, items: List[dict]) -> int:
        """Insert all items for a purchase order. Returns number inserted."""
        count = 0
        for item in items or []:
            try:
                await database.execute(
                    insert(purchase_order_items_table).values(**_clean_item(item, po_id))
                )
                count += 1
            except Exception as e:
                log_error(f"Error inserting purchase order item: {str(e)}")
                raise
        return count

    @staticmethod
    async def get_by_po(po_id: int) -> List[dict]:
        """
        Ambil item PO beserta nama barang/alatnya.

        Satu baris bisa merujuk master_item (PO barang) ATAU master_equipment
        (PO B, penyewaan alat), jadi keduanya di-join agar dokumen yang
        dicetak selalu punya nama.
        """
        try:
            joined = purchase_order_items_table.join(
                master_item_table,
                purchase_order_items_table.c.item_id == master_item_table.c.id,
                isouter=True,
            ).join(
                master_equipment_table,
                purchase_order_items_table.c.equipment_id
                == master_equipment_table.c.id,
                isouter=True,
            )
            # fleet_id is resolved against the hardcoded frontend fleet list,
            # so no fleet join here — the raw fleet_id is returned as-is.
            query = (
                select(
                    *purchase_order_items_table.c,
                    master_item_table.c.sku.label("sku"),
                    master_item_table.c.description.label("item_description"),
                    master_equipment_table.c.name.label("equipment_name"),
                )
                .select_from(joined)
                .where(purchase_order_items_table.c.purchaseOrderID == po_id)
            )
            rows = await database.fetch_all(query)

            hasil = []
            for r in rows:
                d = dict(r)
                # Nama barang diambil dari katalog bila `task` kosong.
                #
                # Baris yang merujuk master_item tidak lagi menyimpan
                # namanya: nama barang bisa jauh lebih panjang daripada
                # kolom `task` (100 karakter), dan menyalinnya berarti
                # dokumen menyimpan nama yang bisa berbeda dari katalognya
                # bila katalog itu diperbaiki.
                #
                # Dokumen lama yang sudah terlanjur menyimpan `task` tetap
                # memakai nilainya sendiri — nama pada dokumen yang sudah
                # terbit tidak boleh berubah.
                if not d.get("task"):
                    d["task"] = d.get("item_description") or d.get(
                        "equipment_name"
                    )
                hasil.append(d)
            return hasil
        except Exception as e:
            log_error(f"Error fetching purchase order items: {str(e)}")
            return []

    @staticmethod
    async def delete_by_po(po_id: int) -> None:
        """Hard-delete all items for a PO (used when re-saving on edit)."""
        try:
            await database.execute(
                delete(purchase_order_items_table).where(
                    purchase_order_items_table.c.purchaseOrderID == po_id
                )
            )
        except Exception as e:
            log_error(f"Error deleting purchase order items: {str(e)}")
            raise

    @staticmethod
    def compute_dpp(items: List[dict], ppn_percent: float) -> float:
        """
        JANGAN DIPAKAI tanpa diperiksa ulang. Tidak dipanggil di mana pun.

        Fungsi ini mengandaikan harga satuan SUDAH TERMASUK PPN, lalu
        mengeluarkannya dengan membagi (1 + ppn/100).

        Seluruh formulir purchase order memakai kebalikannya: harga yang
        diisi adalah DPP, dan PPN ditambahkan di atasnya. Bila fungsi ini
        disambungkan apa adanya, DPP yang tersimpan menjadi sekitar 9,9%
        lebih kecil daripada yang tercetak pada dokumen — dan selisihnya
        tidak terlihat sebagai galat, hanya sebagai angka yang tidak cocok
        saat dibandingkan.

        Bila suatu saat memang dibutuhkan, hapus pembagian PPN-nya.
        """
        total = sum(
            (float(i.get("price") or 0) * float(i.get("quantity") or 1)) for i in (items or [])
        )
        if ppn_percent and ppn_percent > 0:
            return round(total / (1 + ppn_percent / 100), 2)
        return round(total, 2)