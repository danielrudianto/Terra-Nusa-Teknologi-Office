"""
Meilisearch integration for the master_item catalog.
Mirrors utils/meilisearch.py (suppliers) but for its own index so the two
never interfere. Reuses the already-initialised Meilisearch client.
"""
from datetime import datetime
from sqlalchemy import select
from utils.database import database
from utils.logger_utils import log_info, log_error
from utils.meilisearch import client  # reuse the existing client instance
from models.master_item_model import master_item_table

index_name = "master_items"
index = client.index(index_name)

settings = {
    "displayedAttributes": [
        "id", "sku", "description", "brand", "type", "unit", "availablePurchaseType"
    ],
    "searchableAttributes": ["sku", "description", "brand", "type"],
    "filterableAttributes": ["brand", "type", "unit", "availablePurchaseType"],
    "sortableAttributes": ["sku", "brand", "type", "isFavorite"],
    # `exactness` DIDAHULUKAN daripada `typo` dan `proximity`.
    #
    # Pada katalog besi, yang membedakan barang sering hanya satu karakter —
    # D22 dan D25, 16L dan 16T. Dengan urutan bawaan, hasil yang meleset satu
    # huruf dapat menempati peringkat di atas yang persis, sehingga barang
    # yang salah muncul lebih dulu dan tampak seperti jawabannya.
    "rankingRules": ["words", "exactness", "typo", "proximity", "attribute", "sort"],
    "nonSeparatorTokens": [".", ",", "-", "_"],
    "separatorTokens": ["/", "&"],
}

typo_settings = {
    # Kata pendek harus PERSIS.
    #
    # Dengan ambang bawaan 4, "22mm" — yang panjangnya tepat empat —
    # dianggap cocok dengan "25mm". Pada katalog besi itu bukan kesalahan
    # ketik yang wajar dimaafkan, melainkan barang yang berbeda: diameternya
    # tiga milimeter lebih besar, dan dokumennya sudah ditandatangani vendor
    # sebelum ada yang menyadarinya.
    #
    # Ambang enam membuat seluruh sebutan ukuran — 10mm sampai 40mm, D22,
    # 16L — harus diketik benar.
    "minWordSizeForTypos": {"oneTypo": 6, "twoTypos": 10},

    # SKU tidak pernah dimaafkan salah ketik; ia kode, bukan kalimat.
    "disableOnAttributes": ["sku"],
}


def _split_types(value):
    """availablePurchaseType is stored as 'G,B' -> expose as a list for filtering."""
    if not value:
        return []
    return [v.strip() for v in str(value).split(",") if v.strip()]


def to_document(row: dict) -> dict:
    """Build the Meilisearch document from a DB row (dict)."""
    return {
        "id": row["id"],
        "sku": row.get("sku") or "",
        "description": row.get("description") or "",
        "brand": row.get("brand") or "",
        "type": row.get("type") or "",
        "unit": row.get("unit") or "",
        "availablePurchaseType": _split_types(row.get("availablePurchaseType")),
        # Dipakai memutus seri pada PEMILIH barang: `sort=isFavorite:desc`
        # hanya dikirim dari sana, sehingga daftar Master Barang tidak ikut
        # berubah urutannya.
        "isFavorite": bool(row.get("isFavorite") or False),
    }


def index_document(row: dict):
    try:
        index.add_documents([to_document(row)])
    except Exception as e:
        log_error(f"Error indexing master item in search: {str(e)}")


def index_documents(rows: list):
    try:
        if rows:
            index.add_documents([to_document(r) for r in rows])
    except Exception as e:
        log_error(f"Error batch-indexing master items in search: {str(e)}")


def delete_document(item_id: int):
    try:
        index.delete_document(item_id)
    except Exception as e:
        log_error(f"Error removing master item from search index: {str(e)}")


#: Sinonim pencarian katalog barang.
#:
#: Meilisearch memperlakukan sinonim SEARAH: mendaftarkan "hitam" -> ["black"]
#: membuat pencarian "hitam" menemukan "black", tetapi TIDAK sebaliknya.
#: Karena itu tiap pasangan didaftarkan dua arah lewat `_dua_arah()`.
#:
#: Katalognya ditulis campur — sebagian memakai istilah teknis Inggris, sebagian
#: sebutan lapangan. Yang mencari mengetik apa yang ia sebut sehari-hari, dan
#: tanpa sinonim ia menyimpulkan barangnya tidak ada lalu membuat entri kembar.
_PASANGAN = [
    # ---- warna ----
    ("black", ["hitam"]),
    ("white", ["putih"]),
    ("red", ["merah"]),
    ("blue", ["biru"]),
    ("green", ["hijau"]),
    ("yellow", ["kuning"]),
    ("orange", ["oranye", "jingga"]),
    ("grey", ["gray", "abu", "abu-abu"]),
    ("brown", ["coklat", "cokelat"]),
    ("silver", ["perak"]),
    ("gold", ["emas"]),
    ("clear", ["bening", "transparan"]),

    # ---- kelistrikan ----
    # Sebutan lapangan dan istilah katalog kerap berbeda jauh; keduanya
    # dipakai orang yang sama pada hari yang sama.
    ("industrial plug", ["colokan industrial", "steker industrial"]),
    ("wall socket", ["socket", "soket", "stopkontak", "stop kontak"]),
    ("industrial socket", ["soket industrial", "socket industrial"]),
    ("fitting lampu", ["dudukan lampu", "lamp holder"]),

    # ---- perkakas ----
    # "kuku macan" sebutan lapangan yang tidak menyerupai istilah resminya
    # sama sekali — tanpa sinonim, yang mencari tidak akan pernah menemukannya.
    ("wire rope clip", ["kuku macan", "klem seling", "klem sling"]),
]


def _dua_arah(pasangan: list) -> dict:
    """
    Susun peta sinonim DUA ARAH dari daftar pasangan.

    Meilisearch tidak menyimpulkan arah sebaliknya sendiri. Menulisnya manual
    berarti tiap istilah harus disebut berkali-kali, dan yang terlewat tidak
    menimbulkan galat — hanya pencarian yang diam-diam tidak menemukan apa pun
    dari satu arah saja.
    """
    peta: dict[str, set] = {}
    for utama, lainnya in pasangan:
        semua = [utama, *lainnya]
        for kata in semua:
            k = kata.lower()
            peta.setdefault(k, set()).update(x for x in semua if x.lower() != k)
    return {k: sorted(v) for k, v in peta.items()}


item_synonyms = _dua_arah(_PASANGAN)


async def setup_master_item_meilisearch():
    """Ensure the index exists and settings are applied (called on startup)."""
    try:
        client.create_index(index_name, {"primaryKey": "id"})
    except Exception:
        pass
    index.update_settings(settings)
    index.update_typo_tolerance(typo_settings)
    index.update_synonyms(item_synonyms)
    log_info(f"Settings applied to index '{index_name}' successfully.")


async def sync_master_item_meilisearch():
    """Rebuild the index from the database (called on startup)."""
    try:
        try:
            client.create_index(index_name, {"primaryKey": "id"})
        except Exception:
            pass

        index.delete_all_documents()

        query = select(master_item_table).where(master_item_table.c.isDelete == False)
        rows = await database.fetch_all(query)

        docs = []
        for row in rows:
            row_dict = dict(row)
            for key, value in row_dict.items():
                if isinstance(value, datetime):
                    row_dict[key] = value.isoformat()
            docs.append(to_document(row_dict))

        if docs:
            index.add_documents(docs)
        log_info(f"Synced {len(docs)} master items to Meilisearch index '{index_name}'.")
    except Exception as e:
        log_error(f"Error syncing master items to Meilisearch: {str(e)}")
        raise