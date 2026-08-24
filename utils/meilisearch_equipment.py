"""Meilisearch integration for the master_equipment catalogue.
Own index, reuses the shared Meilisearch client."""
from datetime import datetime
from sqlalchemy import select
from utils.database import database
from utils.logger_utils import log_info, log_error
from utils.meilisearch import client
from models.master_equipment_model import master_equipment_table

index_name = "master_equipment"
index = client.index(index_name)

settings = {
    "displayedAttributes": ["id", "name", "category", "capacity", "brand", "unit"],
    "searchableAttributes": ["name", "category", "capacity", "brand"],
    "filterableAttributes": ["category", "brand", "unit"],
    "sortableAttributes": ["name", "category"],
    "rankingRules": ["words", "typo", "proximity", "attribute", "sort", "exactness"],
    "nonSeparatorTokens": [".", ",", "-"],
    "separatorTokens": ["/", "&"],
}


def to_document(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row.get("name") or "",
        "category": row.get("category") or "",
        "capacity": row.get("capacity") or "",
        "brand": row.get("brand") or "",
        "unit": row.get("unit") or "hari",
    }


def index_document(row: dict):
    try:
        index.add_documents([to_document(row)])
    except Exception as e:
        log_error(f"Error indexing master equipment: {str(e)}")


def delete_document(item_id: int):
    try:
        index.delete_document(item_id)
    except Exception as e:
        log_error(f"Error removing master equipment from index: {str(e)}")


async def setup_master_equipment_meilisearch():
    try:
        client.create_index(index_name, {"primaryKey": "id"})
    except Exception:
        pass
    index.update_settings(settings)
    log_info(f"Settings applied to index '{index_name}'.")


async def sync_master_equipment_meilisearch():
    try:
        try:
            client.create_index(index_name, {"primaryKey": "id"})
        except Exception:
            pass
        index.delete_all_documents()
        rows = await database.fetch_all(
            select(master_equipment_table).where(master_equipment_table.c.isDelete == False)
        )
        docs = []
        for row in rows:
            d = dict(row)
            for k, v in d.items():
                if isinstance(v, datetime):
                    d[k] = v.isoformat()
            docs.append(to_document(d))
        if docs:
            index.add_documents(docs)
        log_info(f"Synced {len(docs)} equipment to Meilisearch index '{index_name}'.")
    except Exception as e:
        log_error(f"Error syncing master equipment: {str(e)}")
        raise