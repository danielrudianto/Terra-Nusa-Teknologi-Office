from typing import Dict
from datetime import datetime as dt
from utils.logger_utils import log_info, log_error
from repository.purchase_order_repository import PurchaseOrderRepository
from repository.purchase_order_item_repository import PurchaseOrderItemRepository
from repository.supplier_repository import SupplierRepository


class PurchaseOrderController:
    @staticmethod
    async def generate_purchase_order_name(
        project_code: str = "", purchase_type: str = ""
    ) -> tuple[str, int]:
        """
        Nomor dokumen dengan urutan berjalan per proyek.

        Format: {seq:03d}-SPK-{projectCode}-{purchaseType}
        contoh: 025-SPK-MICZ-G

        Seluruh jenis memakai awalan SPK dan satu deret nomor yang sama.
        Memisahkan deret per jenis akan menghasilkan dua dokumen bernomor 001
        pada proyek yang sama, dan itu menyulitkan saat dokumen dicari kembali.

        Urutan dihitung per proyek: proyek baru mulai dari 001 lagi, dan
        menambah dokumen di satu proyek tidak menggeser nomor proyek lain.

        Nomor lama yang sudah terbit tidak ikut berubah — nomor adalah
        identitas dokumen, dan mengubahnya memutus jejak ke faktur maupun
        pembayaran yang sudah mengacu padanya.
        """
        try:
            if project_code:
                number = await PurchaseOrderRepository.get_next_project_sequence(
                    project_code
                )
            else:
                # tanpa kode proyek, jatuh kembali ke urutan global
                number = (
                    await PurchaseOrderRepository.get_global_purchase_order_count()
                ) + 1
            seq = f"{number:03d}"
            if project_code and purchase_type:
                name = f"{seq}-SPK-{project_code}-{purchase_type}"
            elif project_code:
                name = f"{seq}-SPK-{project_code}"
            else:
                name = seq
            log_info(
                f"Generated purchase order number '{name}' for project '{project_code}'"
            )
            return name, number
        except Exception as e:
            log_error(f"Error generating purchase order name: {str(e)}")
            return str(int(dt.now().timestamp()))[-3:], 0

    @staticmethod
    async def create_purchase_order(purchase_order_data: Dict, user_id: int):
        """Create a new purchase order with an auto-generated number."""
        try:
            project_name = purchase_order_data.get("projectName", "")
            if not project_name:
                return {"error": "Project name is required", "status": 400}

            # pull out helper-only fields that are not columns
            project_code = purchase_order_data.pop("projectCode", None)
            explicit_name = purchase_order_data.pop("name", None)
            # `items` bukan kolom purchase_orders — dipisah dan disimpan
            # ke purchase_order_items setelah PO-nya terbuat.
            items = purchase_order_data.pop("items", None) or []

            # use client-provided PO number, otherwise auto-generate
            if explicit_name:
                purchase_order_name = explicit_name
                purchase_order_number = None
            else:
                (
                    purchase_order_name,
                    purchase_order_number,
                ) = await PurchaseOrderController.generate_purchase_order_name(
                    project_code or "", purchase_order_data.get("purchaseType", "")
                )
            # simpan nomor urutnya, dipakai untuk menghitung PO berikutnya
            purchase_order_data["number"] = purchase_order_number

            # billing_requirements is NOT NULL — default to {} for the trial
            if purchase_order_data.get("billing_requirements") is None:
                purchase_order_data["billing_requirements"] = {}

            # normalize enum -> value if a raw enum slipped through
            status = purchase_order_data.get("status")
            if status is not None and hasattr(status, "value"):
                purchase_order_data["status"] = status.value

            # NOT NULL system columns (MySQL has server defaults, but set them
            # explicitly so it works regardless of driver default handling)
            purchase_order_data.setdefault("revision", 0)
            purchase_order_data.setdefault("isApproved", False)
            purchase_order_data.setdefault("isDelete", False)
            purchase_order_data["name"] = purchase_order_name
            purchase_order_data["createdBy"] = user_id
            purchase_order_data["createdAt"] = dt.now()

            result = await PurchaseOrderRepository.create(purchase_order_data)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}

            # Simpan baris item. Sebelumnya langkah ini tidak ada sama sekali,
            # sehingga purchase_order_items selalu kosong dan dokumen yang
            # dicetak ulang kehilangan seluruh daftar barang.
            po_id = result.get("purchase_order_id") or result.get("id")
            if po_id and items:
                try:
                    inserted = await PurchaseOrderItemRepository.insert_many(
                        po_id, items
                    )
                    log_info(f"Inserted {inserted} item(s) for purchase order {po_id}")
                except Exception as item_error:
                    log_error(
                        f"Error inserting items for purchase order {po_id}: {str(item_error)}"
                    )
                    return {
                        "error": "Purchase order saved but its items failed to save",
                        "status": 500,
                    }

            return {
                "message": "Purchase order created successfully",
                "purchase_order_id": result["purchase_order_id"],
                "purchase_order_name": purchase_order_name,
            }
        except Exception as e:
            log_error(f"Error creating purchase order: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_purchase_order_by_id(purchase_order_id: int):
        """
        Detail PO lengkap dengan item dan data supplier.

        Keduanya dibutuhkan untuk mencetak ulang dokumen; sebelumnya hanya
        baris purchase_orders yang dikembalikan sehingga tabel barang dan
        alamat supplier kosong saat dicetak.
        """
        try:
            result = await PurchaseOrderRepository.get_by_id(purchase_order_id)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}

            result = dict(result)

            items = await PurchaseOrderItemRepository.get_by_po(purchase_order_id)
            result["items"] = items if isinstance(items, list) else []

            supplier_id = result.get("supplierID")
            if supplier_id:
                supplier = await SupplierRepository.get_by_id(supplier_id)
                # get_by_id mengembalikan model pydantic (SupplierResponse),
                # bukan dict — tanpa konversi ini datanya terlewat diam-diam.
                if supplier is not None and not (
                    isinstance(supplier, dict) and "error" in supplier
                ):
                    data = (
                        supplier
                        if isinstance(supplier, dict)
                        else supplier.model_dump()
                    )
                    result["supplier"] = data
                    result["supplierName"] = data.get("name")
                    # Awalan badan usaha ikut dikirim.
                    #
                    # Tanpa ini, cetak ulang dari daftar PO memanggil
                    # `vendorDisplayName(nama, undefined)` dan awalannya
                    # hilang: "PT. Mutiara" tercetak sebagai "Mutiara".
                    # Kolom lain (alamat, kota, NPWP) sudah dikirim sejak
                    # awal — yang ini terlewat.
                    result["supplierPrefix"] = data.get("prefix")
                    result["supplierAddress"] = data.get("address")
                    result["supplierCity"] = ", ".join(
                        x for x in [data.get("city"), data.get("province")] if x
                    )
                    result["supplierNpwp"] = data.get("npwp")

            return result
        except Exception as e:
            log_error(f"Error fetching purchase order: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def get_all_purchase_orders(
        page: int = 1,
        page_size: int = 10,
        keyword: str = None,
        sortBy: str = None,
        sortByDirection: str = "desc",
    ):
        try:
            result = await PurchaseOrderRepository.get_all(
                page, page_size, keyword, sortBy, sortByDirection
            )
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error fetching purchase orders: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update_purchase_order(purchase_order_id: int, fields: Dict, user_id: int):
        try:
            # drop None values so we only update provided fields
            clean = {k: v for k, v in fields.items() if v is not None}
            status = clean.get("status")
            if status is not None and hasattr(status, "value"):
                clean["status"] = status.value
            result = await PurchaseOrderRepository.update(purchase_order_id, clean)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error updating purchase order: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def update_purchase_order_status(purchase_order_id: int, status: str, user_id: int):
        try:
            result = await PurchaseOrderRepository.update_status(purchase_order_id, status, user_id)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error updating purchase order status: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def approve_purchase_order(purchase_order_id: int, user_id: int):
        try:
            result = await PurchaseOrderRepository.approve(purchase_order_id, user_id)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error approving purchase order: {str(e)}")
            return {"error": str(e), "status": 500}

    @staticmethod
    async def delete_purchase_order(purchase_order_id: int, user_id: int):
        try:
            result = await PurchaseOrderRepository.soft_delete(purchase_order_id, user_id)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error deleting purchase order: {str(e)}")
            return {"error": str(e), "status": 500}