import json
from datetime import datetime as dt
from sqlalchemy import insert, select, func, update, or_
from sqlalchemy.exc import IntegrityError
from utils.database import database
from models.purchase_order_model import purchase_orders_table
from models.supplier_model import suppliers_table
from models.user_model import users_table
from utils.logger_utils import log_error

# JSON columns that may come back as strings from the driver and should be dicts
_JSON_COLUMNS = ("customData", "billing_requirements")


def _normalize_row(row):
    """Turn a DB row into a plain dict, decoding JSON columns if they came back as strings."""
    if row is None:
        return None
    data = dict(row)
    for col in _JSON_COLUMNS:
        val = data.get(col)
        if isinstance(val, str):
            try:
                data[col] = json.loads(val)
            except (ValueError, TypeError):
                pass
    return data


class PurchaseOrderRepository:
    @staticmethod
    async def get_project_purchase_order_count(project_name: str) -> int:
        """Count non-deleted purchase orders for a specific project."""
        try:
            query = (
                select(func.count())
                .select_from(purchase_orders_table)
                .where(
                    purchase_orders_table.c.projectName == project_name,
                    purchase_orders_table.c.isDelete == False,
                )
            )
            return await database.fetch_val(query) or 0
        except Exception as e:
            log_error(f"Error counting purchase orders for project {project_name}: {str(e)}")
            return 0

    @staticmethod
    async def next_addendum_number(parent_id: int) -> int:
        """
        Urutan adendum berikutnya untuk satu dokumen induk.

        Dihitung dari MAX, bukan COUNT: adendum yang dihapus lunak tetap
        pernah terbit dan nomornya sudah dipegang vendor. Memakai COUNT
        akan menerbitkan `ADD2` untuk kedua kalinya setelah satu adendum
        dihapus.
        """
        n = await database.fetch_val(
            """
            SELECT MAX(addendumNumber)
            FROM purchase_orders
            WHERE parentPurchaseOrderID = :induk
            """,
            {"induk": parent_id},
        )
        return int(n or 0) + 1

    @staticmethod
    async def sisa_volume_induk(parent_id: int) -> dict:
        """
        Volume yang MASIH TERSISA per baris pekerjaan pada satu induk.

        Dihitung dari induk ditambah seluruh adendum yang sudah terbit —
        karena adendum berisi selisih, penjumlahannya langsung menghasilkan
        keadaan sekarang.

        Baris dicocokkan lewat `item_id` bila ada, dan lewat teks
        pekerjaannya bila tidak. Pencocokan teks memang tidak sempurna;
        yang penting ia tidak pernah MELONGGARKAN penjagaan — baris yang
        gagal dicocokkan dianggap baris baru, sehingga pengurangan atasnya
        tetap tertolak karena sisanya nol.
        """
        rows = await database.fetch_all(
            """
            SELECT i.item_id, i.task, SUM(i.quantity) AS volume
            FROM purchase_order_items i
            JOIN purchase_orders po ON po.id = i.purchaseOrderID
            WHERE (po.id = :induk OR po.parentPurchaseOrderID = :induk)
              AND po.isDelete = 0
            GROUP BY i.item_id, i.task
            """,
            {"induk": parent_id},
        )
        sisa: dict = {}
        for r in rows:
            d = dict(r)
            kunci = PurchaseOrderRepository._kunci_baris(d.get("item_id"), d.get("task"))
            sisa[kunci] = sisa.get(kunci, 0) + float(d.get("volume") or 0)
        return sisa

    @staticmethod
    def _kunci_baris(item_id, task) -> str:
        """
        Kunci pencocokan baris antara adendum dan induknya.

        `item_id` didahulukan karena pasti; teks pekerjaan dipakai bila
        tidak ada, diseragamkan spasi dan huruf besarnya agar perbedaan
        pengetikan yang tidak berarti tidak membuat baris dianggap berbeda.
        """
        if item_id:
            return f"id:{item_id}"
        return "task:" + " ".join(str(task or "").split()).lower()

    @staticmethod
    async def periksa_pengurangan(parent_id: int, items: list) -> list[str]:
        """
        Periksa bahwa pengurangan tidak melampaui yang tersisa.

        Kembaliannya daftar masalah; kosong berarti sah. Dikembalikan
        sebagai daftar, bukan melempar pada yang pertama, supaya yang
        mengisi melihat seluruh barisnya sekaligus dan tidak memperbaiki
        satu per satu.

        Sepadan dengan penjagaan pada pinjaman: `debt` tidak boleh turun di
        bawah jumlah yang sudah dibayarkan. Di sini, volume tidak boleh
        turun di bawah nol.
        """
        sisa = await PurchaseOrderRepository.sisa_volume_induk(parent_id)
        masalah: list[str] = []
        for it in items or []:
            v = float(it.get("quantity") or 0)
            if v >= 0:
                continue
            kunci = PurchaseOrderRepository._kunci_baris(
                it.get("item_id"), it.get("task")
            )
            tersedia = sisa.get(kunci, 0)
            if abs(v) > tersedia + 0.0001:
                nama = it.get("task") or f"baris {kunci}"
                masalah.append(
                    f"{nama}: pengurangan {abs(v):g} melebihi sisa {tersedia:g}"
                )
        return masalah

    @staticmethod
    async def get_addendums(parent_id: int):
        """Seluruh adendum sebuah dokumen, urut nomornya."""
        rows = await database.fetch_all(
            """
            SELECT id, name, addendumNumber, date, dpp, ppn, isDelete
            FROM purchase_orders
            WHERE parentPurchaseOrderID = :induk AND isDelete = 0
            ORDER BY addendumNumber ASC
            """,
            {"induk": parent_id},
        )
        return [dict(r) for r in rows]

    @staticmethod
    async def get_next_project_sequence(project_name: str) -> int:
        """
        Nomor urut berikutnya untuk satu proyek.

        Dibaca dari kolom `number` (MAX + 1), bukan hasil COUNT dan bukan
        hasil parsing teks: COUNT membuat nomor terpakai ulang setelah ada
        PO dihapus, sedangkan parsing ikut mewarisi nomor global lama.
        Baris terhapus tetap dihitung supaya nomor tidak pernah dobel.
        """
        try:
            query = select(func.max(purchase_orders_table.c.number)).where(
                purchase_orders_table.c.projectName == project_name
            )
            highest = await database.fetch_val(query)
            return (highest or 0) + 1
        except Exception as e:
            log_error(
                f"Error getting next sequence for project {project_name}: {str(e)}"
            )
            return 1

    @staticmethod
    async def get_global_purchase_order_count() -> int:
        """Count all non-deleted purchase orders (used for the running PO number)."""
        try:
            query = (
                select(func.count())
                .select_from(purchase_orders_table)
                .where(purchase_orders_table.c.isDelete == False)
            )
            return await database.fetch_val(query) or 0
        except Exception as e:
            log_error(f"Error counting purchase orders: {str(e)}")
            return 0

    @staticmethod
    async def create(purchase_order_data: dict):
        """Create a new purchase order."""
        try:
            query = insert(purchase_orders_table).values(**purchase_order_data)
            result = await database.execute(query)
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="purchase_orders",
                entityID=result,
                action="create",
            )
            return {"purchase_order_id": result}
        except IntegrityError as e:
            log_error(f"Integrity error while creating purchase order: {str(e.orig)}")
            return {"error": "Internal server error.", "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while creating purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_by_id(purchase_order_id: int):
        """
        Satu purchase order yang belum dihapus.

        Nama DAN jabatan penyetuju ikut diambil karena dokumen mencantumkan
        keduanya pada blok tanda tangan. Yang tersimpan di tabel hanya
        `approvedBy` berupa ID; tanpa join ini, dokumen hanya tahu ADA yang
        menyetujui tetapi tidak tahu siapa — dan blok tanda tangannya tidak
        dapat diisi.
        """
        try:
            query = (
                select(
                    *purchase_orders_table.c,
                    users_table.c.name.label("approvedByName"),
                    users_table.c.position.label("approvedByPosition"),
                )
                # Kiri luar: PO yang belum disetujui belum punya `approvedBy`,
                # dan join dalam akan menghilangkannya dari hasil sama sekali.
                .select_from(
                    purchase_orders_table.outerjoin(
                        users_table,
                        purchase_orders_table.c.approvedBy == users_table.c.id,
                    )
                )
                .where(
                    purchase_orders_table.c.id == purchase_order_id,
                    purchase_orders_table.c.isDelete == False,
                )
            )
            result = await database.fetch_one(query)
            if not result:
                return {"error": "Purchase order not found", "status": 404}
            return _normalize_row(result)
        except Exception as e:
            log_error(f"Unexpected error while fetching purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    # Kolom yang boleh dipakai mengurutkan. Daftar putih ini mencegah nama

    # kolom sembarang ikut masuk ke query.

    SORTABLE = {

        "date": purchase_orders_table.c.date,

        "value": purchase_orders_table.c.dpp,

        "supplier": suppliers_table.c.name,

        "project": purchase_orders_table.c.projectName,

        "name": purchase_orders_table.c.name,

        # Tabel ini tidak punya kolom "status"; yang setara adalah isApproved.
        "status": purchase_orders_table.c.isApproved,

    }


    @staticmethod
    def _order_clause(sortBy: str = None, sortByDirection: str = "desc"):
        """Kolom pengurut; jatuh ke createdAt bila kolomnya tidak dikenal."""
        column = PurchaseOrderRepository.SORTABLE.get(
            sortBy, purchase_orders_table.c.createdAt
        )
        return (
            column.asc()
            if str(sortByDirection).lower() == "asc"
            else column.desc()
        )


    @staticmethod
    async def get_all(
        page: int = 1,
        page_size: int = 10,
        keyword: str = None,
        sortBy: str = None,
        sortByDirection: str = "desc",
    ):
        """
        Get purchase orders with pagination (newest first).

        `keyword` mencari pada nomor PO dan nama proyek (tabel ini tidak
        menyimpan nama supplier, hanya supplierID).
        Sebelumnya parameter ini tidak ada padahal controller mengirimnya,
        sehingga daftar PO gagal dimuat.
        """
        try:
            offset = (page - 1) * page_size

            conditions = [purchase_orders_table.c.isDelete == False]
            if keyword:
                pattern = f"%{keyword}%"
                conditions.append(
                    or_(
                        purchase_orders_table.c.name.ilike(pattern),
                        purchase_orders_table.c.projectName.ilike(pattern),
                    )
                )

            # Join ke suppliers: daftar PO menampilkan nama supplier, dan
            # sebelumnya kolom itu tidak ikut diambil sehingga tampil "?".
            query = (
                select(
                    purchase_orders_table,
                    suppliers_table.c.name.label("supplier_name"),
                    suppliers_table.c.prefix.label("supplier_prefix"),
                )
                .select_from(
                    purchase_orders_table.outerjoin(
                        suppliers_table,
                        purchase_orders_table.c.supplierID == suppliers_table.c.id,
                    )
                )
                .where(*conditions)
                .order_by(PurchaseOrderRepository._order_clause(sortBy, sortByDirection))
                .offset(offset)
                .limit(page_size)
            )
            rows = await database.fetch_all(query)

            count_query = (
                select(func.count())
                .select_from(purchase_orders_table)
                .where(*conditions)
            )
            total_count = await database.fetch_val(count_query) or 0

            return {
                "data": [_normalize_row(r) for r in rows],
                "count": total_count,
                "page": page,
                "page_size": page_size,
            }
        except Exception as e:
            log_error(f"Unexpected error while fetching purchase orders: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update(
        purchase_order_id: int,
        fields: dict,
        user_id: int = None,
        user_name: str = None,
    ):
        """Update editable fields of a purchase order and bump its revision."""
        try:
            if not fields:
                return {"message": "No changes"}

            # Keadaan sebelum diubah diambil lebih dulu; setelah update,
            # nilai lamanya sudah tertimpa dan tidak bisa direkam lagi.
            sebelum = await database.fetch_one(
                select(purchase_orders_table).where(
                    purchase_orders_table.c.id == purchase_order_id
                )
            )

            query = (
                update(purchase_orders_table)
                .where(purchase_orders_table.c.id == purchase_order_id)
                .values(revision=purchase_orders_table.c.revision + 1, **fields)
            )
            await database.execute(query)

            # Impor lokal agar modul repository tidak saling bergantung
            # saat dimuat.
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="purchase_orders",
                entityID=purchase_order_id,
                action="update",
                userID=user_id,
                userName=user_name,
                changes=AuditLogRepository.diff(
                    dict(sebelum) if sebelum else {}, fields
                ),
            )

            return {"message": "Purchase order updated successfully"}
        except IntegrityError as e:
            log_error(f"Integrity error while updating purchase order: {str(e.orig)}")
            return {"error": "Internal server error.", "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while updating purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update_status(purchase_order_id: int, status: str, user_id: int):
        """Update only the status of a purchase order."""
        try:
            # Keadaan sebelum & sesudah dibandingkan agar nilai lama ikut
            # terekam; tanpa ini audit hanya tahu "diubah", bukan "dari apa".
            _sebelum = await database.fetch_one(
                select(purchase_orders_table).where(purchase_orders_table.c.id == purchase_order_id)
            )
            query = (
                update(purchase_orders_table)
                .where(purchase_orders_table.c.id == purchase_order_id)
                .values(status=status)
            )
            await database.execute(query)
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="purchase_orders",
                entityID=purchase_order_id,
                action="update_status",
                userID=user_id,
                changes=AuditLogRepository.diff(
                    dict(_sebelum) if _sebelum else {},
                    dict(
                        await database.fetch_one(
                            select(purchase_orders_table).where(
                                purchase_orders_table.c.id == purchase_order_id
                            )
                        )
                        or {}
                    ),
                ),
            )
            
            return {"message": "Purchase order status updated successfully"}
        except Exception as e:
            log_error(f"Unexpected error while updating purchase order status: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def approve(purchase_order_id: int, user_id: int):
        """Mark a purchase order as approved."""
        try:
            query = (
                update(purchase_orders_table)
                .where(purchase_orders_table.c.id == purchase_order_id)
                .values(
                    isApproved=True,
                    approvedBy=user_id,
                    approvedAt=dt.now(),
                    status="approved",
                )
            )
            await database.execute(query)
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="purchase_orders",
                entityID=purchase_order_id,
                action="approve",
                userID=user_id,
            )

            return {"message": "Purchase order approved successfully"}
        except Exception as e:
            log_error(f"Unexpected error while approving purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def soft_delete(purchase_order_id: int, user_id: int):
        """Soft delete a purchase order."""
        try:
            query = (
                update(purchase_orders_table)
                .where(purchase_orders_table.c.id == purchase_order_id)
                .values(isDelete=True, deletedBy=user_id, deletedAt=dt.now())
            )
            await database.execute(query)
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="purchase_orders",
                entityID=purchase_order_id,
                action="delete",
                userID=user_id,
            )

            return {"message": "Purchase order deleted successfully"}
        except Exception as e:
            log_error(f"Unexpected error while deleting purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}