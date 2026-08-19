from sqlalchemy import (
    Table, Column, Integer, String, Text, DECIMAL, ForeignKey, text,
)
from utils.database import metadata

purchase_order_items_table = Table(
    "purchase_order_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # Barang katalog (master_item) — PO G, F, C, 5.1.1, 5.1.2, 5.1.6, 6.3
    Column("item_id", Integer, ForeignKey("master_item.id"), nullable=True),
    # Alat sewa (master_equipment) — khusus PO B (penyewaan alat kerja)
    Column("equipment_id", Integer, nullable=True),
    Column("fleet_id", Integer, nullable=True),  # references hardcoded frontend fleet list (no DB table)
    Column("task", String(100), nullable=True),
    Column("quantity", DECIMAL(12, 2), nullable=False, server_default="0.00"),
    Column("price", DECIMAL(14, 4), nullable=False, server_default="0.0000"),
    Column("remarks_1", Text, nullable=True),
    Column("remarks_2", Text, nullable=True),
    Column("remarks_3", Text, nullable=True),
    Column("remarks_4", Text, nullable=True),
    # Penanggung jawab per baris. Dipakai pada SPK jasa antar berbasis
    # aplikasi: satu SPK memuat banyak pengiriman yang ditangani orang
    # berbeda, sehingga PIC tidak bisa ditaruh di tingkat kontrak.
    Column("remarks_5", Text, nullable=True),
    Column("remarks_6", Text, nullable=True),
    Column("unit", String(45), nullable=False, server_default=""),
    Column("purchaseOrderID", Integer, ForeignKey("purchase_orders.id"), nullable=False),
)