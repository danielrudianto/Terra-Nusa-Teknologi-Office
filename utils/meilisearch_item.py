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
    "sortableAttributes": ["sku", "brand", "type"],
    "rankingRules": ["words", "typo", "proximity", "attribute", "sort", "exactness"],
    "nonSeparatorTokens": [".", ",", "-", "_"],
    "separatorTokens": ["/", "&"],
}

typo_settings = {
    "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 8},
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


async def setup_master_item_meilisearch():
    """Ensure the index exists and settings are applied (called on startup)."""
    try:
        client.create_index(index_name, {"primaryKey": "id"})
    except Exception:
        pass
    index.update_settings(settings)
    index.update_typo_tolerance(typo_settings)
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