from typing import List, Optional, Dict, Any
from sqlalchemy import and_, case, delete, func, insert, select, update
from utils.database import database
from utils.logger_utils import log_error
from sqlalchemy.exc import IntegrityError
from datetime import datetime as dt
from models.supplier_model import suppliers_table
from schemas.supplier_schema import SupplierCreate, SupplierUpdate, SupplierResponse
from utils.errors import internal_error

class SupplierRepository:
    @staticmethod
    async def laporan(
        supplier_id: int,
        date_from: str = None,
        date_to: str = None,
        project_name: str = None,
    ):
        """
        Laporan satu pemasok: ringkasan nilai, sebaran proyek, dokumen terakhir.

        Dihitung dari PEMBELIAN, bukan purchase order. Purchase order adalah
        pesanan — sebagian tidak pernah ditagih, sebagian lain ditagih dengan
        nilai berbeda karena volume terpasang tidak sama dengan yang dipesan.
        Yang menentukan hubungan dagang dengan pemasok adalah apa yang
        benar-benar ditagihkan.
        """
        from models.purchase_model import purchases_table
        from models.payment_outgoing_model import payments_outgoing_table

        try:
            syarat = [
                purchases_table.c.supplierID == supplier_id,
                purchases_table.c.isDelete == False,
            ]
            if date_from:
                syarat.append(purchases_table.c.date >= date_from)
            if date_to:
                syarat.append(purchases_table.c.date <= date_to)
            if project_name:
                syarat.append(purchases_table.c.projectName == project_name)

            # Nilai tagihan sebuah pembelian.
            #
            # PPn disimpan sebagai PERSEN, bukan rupiah — mengalikannya
            # langsung menghasilkan angka yang terlalu kecil sepersekian
            # ribu kali.
            nilai = (
                purchases_table.c.dpp
                + (purchases_table.c.ppn * purchases_table.c.dpp / 100)
                + func.coalesce(purchases_table.c.pbbkb, 0)
            )

            ringkas = await database.fetch_one(
                select(
                    func.count().label("jumlah"),
                    func.coalesce(func.sum(nilai), 0).label("total"),
                    func.coalesce(
                        func.sum(
                            case((purchases_table.c.isPaid == False, nilai), else_=0)
                        ),
                        0,
                    ).label("belum_dibayar"),
                    # Lewat tempo: belum lunas DAN tanggal jatuh temponya
                    # sudah lewat. Keduanya harus benar; yang belum lunas
                    # tetapi belum jatuh tempo bukan tunggakan.
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    and_(
                                        purchases_table.c.isPaid == False,
                                        purchases_table.c.dueDate.isnot(None),
                                        purchases_table.c.dueDate < func.curdate(),
                                    ),
                                    nilai,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("lewat_tempo"),
                ).where(*syarat)
            )

            proyek = await database.fetch_all(
                select(
                    purchases_table.c.projectName,
                    func.coalesce(func.sum(nilai), 0).label("total"),
                    func.count().label("jumlah"),
                )
                .where(*syarat)
                .group_by(purchases_table.c.projectName)
                .order_by(func.sum(nilai).desc())
            )

            # Lima dokumen terakhir; yang membuka laporan ingin gambaran,
            # bukan seluruh riwayat. Daftar penuh ada di layar Pembelian.
            terakhir = await database.fetch_all(
                select(
                    purchases_table.c.id,
                    purchases_table.c.invoiceName,
                    purchases_table.c.purchaseOrderName,
                    purchases_table.c.projectName,
                    purchases_table.c.date,
                    purchases_table.c.dueDate,
                    purchases_table.c.isPaid,
                    nilai.label("nilai"),
                )
                .where(*syarat)
                .order_by(purchases_table.c.date.desc(), purchases_table.c.id.desc())
                .limit(5)
            )

            return {
                "ringkasan": {
                    "jumlah": int(ringkas["jumlah"] or 0),
                    "total": float(ringkas["total"] or 0),
                    "belumDibayar": float(ringkas["belum_dibayar"] or 0),
                    "lewatTempo": float(ringkas["lewat_tempo"] or 0),
                },
                "proyek": [
                    {
                        "projectName": r["projectName"],
                        "total": float(r["total"] or 0),
                        "jumlah": int(r["jumlah"] or 0),
                    }
                    for r in proyek
                ],
                "terakhir": [
                    {
                        "id": r["id"],
                        "invoiceName": r["invoiceName"],
                        "purchaseOrderName": r["purchaseOrderName"],
                        "projectName": r["projectName"],
                        "date": r["date"],
                        "dueDate": r["dueDate"],
                        "isPaid": bool(r["isPaid"]),
                        "nilai": float(r["nilai"] or 0),
                    }
                    for r in terakhir
                ],
            }
        except Exception as e:
            log_error(f"Error building supplier report: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def create(supplier_data: SupplierCreate) -> Dict[str, Any]:
        """
        Create a new supplier in the database.
        """
        try:
            query = insert(suppliers_table).values(
                **supplier_data.model_dump(exclude_none=True),
                createdAt=dt.now().isoformat(),
                isDelete=False,
                isBlacklist=False
            )
            supplier_id = await database.execute(query)
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="suppliers",
                entityID=supplier_id,
                action="create",
            )
            return {"message": "Supplier created successfully", "supplier_id": supplier_id}
        except IntegrityError as e:
            log_error(f"Integrity error while creating supplier: {str(e)}")
            return {"error": "Something wrong with your input.", "status": 400}
        except Exception as e:
            log_error(f"Error creating supplier: {str(e)}")
            return internal_error()

    @staticmethod
    async def update(supplier_id: int, supplier_data: SupplierUpdate) -> Dict[str, Any]:
        """
        Update an existing supplier.
        """
        try:
            # Keadaan sebelum & sesudah dibandingkan agar nilai lama ikut
            # terekam; tanpa ini audit hanya tahu "diubah", bukan "dari apa".
            _sebelum = await database.fetch_one(
                select(suppliers_table).where(suppliers_table.c.id == supplier_id)
            )
            update_values = supplier_data.model_dump(exclude_none=True)
            update_values['updatedAt'] = dt.now().isoformat()
            
            query = (
                update(suppliers_table)
                .where(suppliers_table.c.id == supplier_id)
                .values(update_values)
            )
            
            await database.execute(query)
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="suppliers",
                entityID=supplier_id,
                action="update",
                changes=AuditLogRepository.diff(
                    dict(_sebelum) if _sebelum else {},
                    dict(
                        await database.fetch_one(
                            select(suppliers_table).where(
                                suppliers_table.c.id == supplier_id
                            )
                        )
                        or {}
                    ),
                ),
            )

            return {"message": "Supplier updated successfully", "supplier_id": supplier_id}
        except IntegrityError as e:
            log_error(f"Integrity error while updating supplier: {str(e)}")
            return {"error": "Something wrong with your input.", "status": 400}
        except Exception as e:
            log_error(f"Error updating supplier: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_by_id(supplier_id: int) -> Optional[SupplierResponse]:
        """
        Get a supplier by ID from the database.
        """
        try:
            query = select(suppliers_table).where(
                suppliers_table.c.id == supplier_id,
                suppliers_table.c.isDelete == False
            )
            result = await database.fetch_one(query)
            return SupplierResponse.model_validate(dict(result)) if result else None
        except Exception as e:
            log_error(f"Error fetching supplier by ID: {str(e)}")
            raise

    @staticmethod
    async def get_all(
        skip: int = 0,
        limit: int = 100,
        keyword: str = None,
        sortBy: str = None,
        sortByDirection: str = "asc",
    ) -> List[SupplierResponse]:
        """
        Get all suppliers with optional pagination and keyword search.
        """
        try:
            query = select(suppliers_table).where(
                suppliers_table.c.isDelete == False
            )
            
            if keyword:
                keyword_filter = f"%{keyword}%"
                query = query.where(
                    suppliers_table.c.name.ilike(keyword_filter) |
                    suppliers_table.c.address.ilike(keyword_filter) |
                    suppliers_table.c.city.ilike(keyword_filter) |
                    suppliers_table.c.province.ilike(keyword_filter) |
                    suppliers_table.c.phoneNumber.ilike(keyword_filter) |
                    suppliers_table.c.email.ilike(keyword_filter) |
                    suppliers_table.c.itemsSold.ilike(keyword_filter) |
                    suppliers_table.c.serviceArea.ilike(keyword_filter)
                )
            
            # Kolom yang boleh dipakai mengurutkan; daftar putih mencegah nama
            
            # kolom sembarang ikut masuk ke query.
            
            SORTABLE = {
            
                "name": suppliers_table.c.name,
            
                "city": suppliers_table.c.city,
            
                "npwp": suppliers_table.c.npwp,
            
            }
            
            _kolom = SORTABLE.get(sortBy, suppliers_table.c.name)
            
            query = query.order_by(
            
                _kolom.desc()
            
                if str(sortByDirection).lower() == "desc"
            
                else _kolom.asc()
            
            )

            
            query = query.offset(skip).limit(limit)
            result = await database.fetch_all(query)
            return [SupplierResponse.model_validate(dict(row)) for row in result]
        except Exception as e:
            log_error(f"Error fetching suppliers: {str(e)}")
            raise

    @staticmethod
    async def get_paginated(
        page: int = 1,
        page_size: int = 10,
        keyword: str = None,
        is_blacklist: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Get paginated suppliers with total count.
        """
        try:
            # Base query for data
            data_query = select(suppliers_table).where(
                suppliers_table.c.isDelete == False
            )
            
            # Base query for count
            count_query = select(func.count()).select_from(suppliers_table).where(
                suppliers_table.c.isDelete == False
            )

            # Filter by blacklist status when specified
            if is_blacklist is not None:
                data_query = data_query.where(
                    suppliers_table.c.isBlacklist == is_blacklist
                )
                count_query = count_query.where(
                    suppliers_table.c.isBlacklist == is_blacklist
                )
            
            if keyword:
                keyword_filter = f"%{keyword}%"
                where_condition = (
                    suppliers_table.c.name.ilike(keyword_filter) |
                    suppliers_table.c.address.ilike(keyword_filter) |
                    suppliers_table.c.city.ilike(keyword_filter) |
                    suppliers_table.c.province.ilike(keyword_filter) |
                    suppliers_table.c.phoneNumber.ilike(keyword_filter) |
                    suppliers_table.c.email.ilike(keyword_filter) |
                    suppliers_table.c.itemsSold.ilike(keyword_filter) |
                    suppliers_table.c.serviceArea.ilike(keyword_filter)
                )
                data_query = data_query.where(where_condition)
                count_query = count_query.where(where_condition)
            
            # Apply pagination to data query
            offset = (page - 1) * page_size
            data_query = data_query.offset(offset).limit(page_size)
            
            # Execute queries
            suppliers_data = await database.fetch_all(data_query)
            total_count = await database.fetch_val(count_query)
            
            suppliers = [SupplierResponse.model_validate(dict(row)) for row in suppliers_data]
            
            return {
                "data": suppliers,
                "count": len(suppliers),
                "total_count": total_count or 0,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_count + page_size - 1) // page_size if total_count else 0
            }
        except Exception as e:
            log_error(f"Error fetching paginated suppliers: {str(e)}")
            raise

    @staticmethod
    async def soft_delete(supplier_id: int, deleted_by: int) -> Dict[str, Any]:
        """
        Soft delete a supplier by setting isDelete to True.
        """
        try:
            query = (
                update(suppliers_table)
                .where(suppliers_table.c.id == supplier_id)
                .values(
                    isDelete=True,
                    deletedBy=deleted_by,
                    deletedAt=dt.now().isoformat()
                )
            )
            await database.execute(query)
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="suppliers",
                entityID=supplier_id,
                action="delete",
            )
            
            return {"message": "Supplier deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting supplier: {str(e)}")
            return internal_error()

    @staticmethod
    async def set_blacklist(supplier_id: int, is_blacklist: bool,
                            reason: str, user_id: int) -> Dict[str, Any]:
        """Flag or unflag a supplier as blacklisted (warning only)."""
        try:
            values = {"isBlacklist": is_blacklist}
            if is_blacklist:
                values["blacklistReason"] = reason
                values["blacklistedBy"] = user_id
                values["blacklistedAt"] = dt.now().isoformat()
            else:
                values["blacklistReason"] = None
                values["blacklistedBy"] = None
                values["blacklistedAt"] = None

            query = (
                update(suppliers_table)
                .where(suppliers_table.c.id == supplier_id)
                .values(**values)
            )
            await database.execute(query)
            action = "blacklisted" if is_blacklist else "un-blacklisted"
            return {"message": f"Supplier {action} successfully"}
        except Exception as e:
            log_error(f"Error updating supplier blacklist: {str(e)}")
            return internal_error()

    @staticmethod
    async def search_by_keyword(keyword: str) -> List[SupplierResponse]:
        """
        Search suppliers by keyword across multiple fields.
        """
        try:
            if not keyword:
                return await SupplierRepository.get_all()
                
            keyword_filter = f"%{keyword}%"
            query = select(suppliers_table).where(
                suppliers_table.c.isDelete == False
            ).where(
                suppliers_table.c.name.ilike(keyword_filter) |
                suppliers_table.c.address.ilike(keyword_filter) |
                suppliers_table.c.city.ilike(keyword_filter) |
                suppliers_table.c.province.ilike(keyword_filter) |
                suppliers_table.c.phoneNumber.ilike(keyword_filter) |
                suppliers_table.c.email.ilike(keyword_filter) |
                suppliers_table.c.itemsSold.ilike(keyword_filter) |
                suppliers_table.c.serviceArea.ilike(keyword_filter)
            )
            
            result = await database.fetch_all(query)
            return [SupplierResponse.model_validate(dict(row)) for row in result]
        except Exception as e:
            log_error(f"Error searching suppliers: {str(e)}")
            raise