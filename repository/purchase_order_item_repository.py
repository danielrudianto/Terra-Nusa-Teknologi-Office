from typing import List
from sqlalchemy import insert, select, delete
from utils.database import database
from utils.logger_utils import log_error
from models.purchase_order_item_model import purchase_order_items_table
from models.master_item_model import master_item_table

_COLUMNS = [
    "equipment_id", "fleet_id", "task", "quantity", "price",
    "remarks_1", "remarks_2", "remarks_3", "remarks_4", "unit",
]


def _clean_item(item: dict, po_id: int) -> dict:
    row = {"purchaseOrderID": po_id}
    for c in _COLUMNS:
        row[c] = item.get(c)
    # NOT NULL columns with sensible fallbacks
    row["quantity"] = row.get("quantity") or 0
    row["price"] = row.get("price") or 0
    row["unit"] = row.get("unit") or ""
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
        """Fetch items for a PO, joined with fleet + master_item for display."""
        try:
            joined = purchase_order_items_table.join(
                master_item_table,
                purchase_order_items_table.c.equipment_id == master_item_table.c.id,
                isouter=True,
            )
            # fleet_id is resolved against the hardcoded frontend fleet list,
            # so no fleet join here — the raw fleet_id is returned as-is.
            query = (
                select(
                    *purchase_order_items_table.c,
                    master_item_table.c.sku.label("sku"),
                    master_item_table.c.description.label("item_description"),
                )
                .select_from(joined)
                .where(purchase_order_items_table.c.purchaseOrderID == po_id)
            )
            rows = await database.fetch_all(query)
            return [dict(r) for r in rows]
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
        """Server-side DPP from items: total = Σ(price*qty); strip PPN if included."""
        total = sum(
            (float(i.get("price") or 0) * float(i.get("quantity") or 1)) for i in (items or [])
        )
        if ppn_percent and ppn_percent > 0:
            return round(total / (1 + ppn_percent / 100), 2)
        return round(total, 2)