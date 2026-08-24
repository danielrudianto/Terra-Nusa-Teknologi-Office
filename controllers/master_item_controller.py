import csv
import io
from typing import Dict, Any, List
from sqlalchemy.exc import IntegrityError
from utils.logger_utils import log_error, log_info
from utils.meilisearch import client
from utils.meilisearch_item import (
    index_document,
    index_documents,
    delete_document,
)
from schemas.master_item_schema import MasterItemCreate, MasterItemUpdate
from repository.master_item_repository import MasterItemRepository
from utils.errors import internal_error

INDEX_NAME = "master_items"

# Accept both the English column names and the Indonesian import template headers.
HEADER_MAP = {
    "sku": "sku",
    "description": "description",
    "deskripsi": "description",
    "brand": "brand",
    "type": "type",
    "tipe": "type",
    "unit": "unit",
    "satuan": "unit",
    "availablepurchasetype": "availablePurchaseType",
    "tipe po": "availablePurchaseType",
    "tipepo": "availablePurchaseType",
}

REQUIRED_FIELDS = ["sku", "description", "brand", "type", "unit"]


class MasterItemController:
    @staticmethod
    async def create_master_item(item_data: dict, user_id: int) -> Dict[str, Any]:
        log_info(f"Creating master item: {item_data.get('sku')}")
        try:
            item_data["createdBy"] = user_id
            item_create = MasterItemCreate(**item_data)

            # DB-agnostic duplicate check (don't rely on driver-specific exceptions)
            existing = await MasterItemRepository.get_existing_skus([item_create.sku])
            if item_create.sku in existing:
                return {"error": "SKU already exists.", "status": 400}

            result = await MasterItemRepository.create(item_create)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}

            item_id = result["master_item_id"]
            index_document({**item_create.model_dump(), "id": item_id})
            return result
        except IntegrityError:
            return {"error": "SKU already exists.", "status": 400}
        except Exception as e:
            log_error(f"Unexpected error creating master item: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_master_item(item_id: int) -> Dict[str, Any]:
        try:
            item = await MasterItemRepository.get_by_id(item_id)
            if not item:
                return {"error": "Master item not found.", "status": 404}
            return item.model_dump()
        except Exception as e:
            log_error(f"Error fetching master item: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_master_items(
        keyword: str = "", page: int = 1, page_size: int = 10,
        purchase_type: str = None, brand: str = None, item_type: str = None,
        sortBy: str = None,
        sortByDirection: str = "asc",
        favorit_dulu: bool = False,
    ) -> Dict[str, Any]:
        """Search via Meilisearch, fall back to the database if it's unavailable.

        When purchase_type is given (e.g. "G"), only items whose availablePurchaseType
        contains that code are returned.
        """
        try:
            try:
                search_params = {"limit": page_size, "offset": (page - 1) * page_size}

                # Meilisearch hanya menerima kolom yang terdaftar sebagai
                # sortableAttributes; nama lain diabaikan agar tidak menggagalkan
                # pencarian.
                _sortable = ["sku", "brand", "type"]
                if sortBy in _sortable:
                    _arah = "desc" if str(sortByDirection).lower() == "desc" else "asc"
                    search_params["sort"] = [f"{sortBy}:{_arah}"]
                filters = []
                if purchase_type:
                    # availablePurchaseType is indexed as a list -> `= "G"` matches membership
                    filters.append(f'availablePurchaseType = "{purchase_type}"')
                if brand:
                    filters.append(f'brand = "{brand}"')
                if item_type:
                    filters.append(f'type = "{item_type}"')
                if filters:
                    search_params["filter"] = " AND ".join(filters)
                # Seluruh kata harus ada, bukan sebagian.
                #
                # Bawaan Meilisearch adalah `last`: bila tidak ada barang yang
                # memuat semua kata, kata TERAKHIR dibuang lalu dicari lagi,
                # berulang sampai ada hasil. Pencarian "besi ulir 22mm" karena
                # itu akhirnya menjadi pencarian "besi" saja — dan mata
                # gerinda besi ikut muncul di antara tulangan sirip.
                #
                # Dengan `all`, kueri yang meleset menghasilkan daftar KOSONG.
                # Itu disengaja: daftar kosong jelas artinya, sedangkan daftar
                # yang melebar membuat orang memilih barang yang salah — dan
                # D22 tertukar D25 pada dokumen yang ditandatangani vendor
                # jauh lebih mahal daripada mengetik ulang.
                search_params["matchingStrategy"] = "all"

                result = client.index(INDEX_NAME).search(keyword or "", search_params)
                hits = result["hits"]
                jumlah = result.get("estimatedTotalHits", len(hits))

                # Bila kosong, tawarkan yang MENDEKATI — terpisah, bukan
                # dicampur.
                #
                # Dipisah supaya yang membaca tahu ia sedang melihat saran,
                # bukan hasil. Mencampurnya mengembalikan persoalan semula:
                # barang yang tidak dicari muncul seolah-olah cocok.
                """
                Bila kosong, dicoba ulang dengan SINONIMNYA lebih dulu.

                Katalog ini memuat dua bahasa sekaligus — `wrench` dan `kunci`
                sama-sama 175 kali — dan sebagian salah eja terlanjur
                tersimpan: `stanless` 191 kali berbanding `stainless` 31.

                Dicoba SETELAH pencarian biasa, bukan menggantikannya: yang
                mengetik kata yang memang ada di katalog harus mendapat
                hasilnya sendiri lebih dulu, tanpa dicampur bentuk lain yang
                mungkin lebih banyak jumlahnya.
                """
                if keyword and not hits:
                    from constants.sinonim_barang import perluas_kata_kunci

                    bentuk = perluas_kata_kunci(keyword)
                    # Bentuk pertama adalah kata aslinya, yang sudah dicoba.
                    for lain in bentuk[1:]:
                        try:
                            ulang = client.index(INDEX_NAME).search(
                                lain, search_params
                            )
                        except Exception as e:
                            log_error(f"Gagal mencari sinonim '{lain}': {str(e)}")
                            continue
                        if ulang["hits"]:
                            hits = ulang["hits"]
                            jumlah = ulang.get(
                                "estimatedTotalHits", len(ulang["hits"])
                            )
                            break

                saran = []
                if keyword and not hits:
                    longgar = dict(search_params)
                    longgar["matchingStrategy"] = "last"
                    longgar["limit"] = 5
                    longgar["offset"] = 0
                    longgar.pop("sort", None)
                    try:
                        saran = client.index(INDEX_NAME).search(keyword, longgar)["hits"]
                    except Exception as e:
                        # Saran adalah pelengkap; kegagalannya tidak boleh
                        # menggagalkan pencarian yang sudah berhasil.
                        log_error(f"Gagal menyusun saran pencarian: {str(e)}")

                return {
                    "data": hits,
                    "count": jumlah,
                    "page": page,
                    "page_size": page_size,
                    "suggestions": saran,
                }
            except Exception as search_error:
                log_error(f"Meilisearch error, falling back to database: {str(search_error)}")
                return await MasterItemRepository.get_paginated(
                    page, page_size, keyword or None, purchase_type, brand,
                    item_type, sortBy, sortByDirection, favorit_dulu)
        except Exception as e:
            log_error(f"Error fetching master items: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def set_favorite(item_id: int, favorit: bool) -> Dict[str, Any]:
        """
        Tandai favorit, lalu segarkan indeks pencariannya.

        Indeksnya HARUS ikut diperbarui: urutan pada pemilih barang dibaca
        dari sana, sehingga tanpa ini penandaannya tersimpan tetapi tidak
        mengubah apa pun yang terlihat.
        """
        hasil = await MasterItemRepository.set_favorite(item_id, favorit)
        if isinstance(hasil, dict) and "error" in hasil:
            return hasil
        try:
            index_document(hasil)
        except Exception as e:
            # Penandaannya sudah tersimpan; kegagalan indeks tidak boleh
            # membatalkannya. Sinkronisasi berkala akan menyusul.
            log_error(f"Error indexing favorite item {item_id}: {str(e)}")
        return hasil

    @staticmethod
    async def get_facets() -> Dict[str, Any]:
        """Daftar brand & type unik untuk dropdown filter."""
        try:
            return await MasterItemRepository.get_facets()
        except Exception as e:
            log_error(f"Error fetching facets: {str(e)}")
            return {"brands": [], "types": []}

    @staticmethod
    async def update_master_item(item_data: dict, user_id: int) -> Dict[str, Any]:
        try:
            if "id" not in item_data:
                return {"error": "Master item ID is required for update", "status": 400}
            item_id = item_data["id"]

            existing = await MasterItemRepository.get_by_id(item_id)
            if not existing:
                return {"error": "Master item not found", "status": 404}

            item_data["updatedBy"] = user_id
            item_update = MasterItemUpdate(**item_data)
            result = await MasterItemRepository.update(item_id, item_update)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}

            merged = {**existing.model_dump(), **item_update.model_dump(exclude_none=True), "id": item_id}
            index_document(merged)
            return result
        except IntegrityError:
            return {"error": "SKU already exists.", "status": 400}
        except Exception as e:
            log_error(f"Unexpected error updating master item: {str(e)}")
            return internal_error()

    @staticmethod
    async def delete_master_item(item_id: int, user_id: int) -> Dict[str, Any]:
        try:
            existing = await MasterItemRepository.get_by_id(item_id)
            if not existing:
                return {"error": "Master item not found", "status": 404}

            result = await MasterItemRepository.soft_delete(item_id, user_id)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}

            delete_document(item_id)
            return result
        except Exception as e:
            log_error(f"Error deleting master item: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def import_csv(file_bytes: bytes, user_id: int) -> Dict[str, Any]:
        """
        Parse a CSV and bulk-insert new master items.
        - accepts English or Indonesian template headers
        - skips rows whose SKU already exists (DB) or is duplicated within the file
        - collects per-row validation errors without aborting the whole import
        """
        try:
            text_stream = io.StringIO(file_bytes.decode("utf-8-sig"))
            reader = csv.DictReader(text_stream)

            if not reader.fieldnames:
                return {"error": "CSV kosong atau tidak ada header.", "status": 400}

            # normalize headers -> canonical field names
            col_to_field = {}
            for col in reader.fieldnames:
                key = (col or "").strip().lower()
                if key in HEADER_MAP:
                    col_to_field[col] = HEADER_MAP[key]

            missing = [f for f in REQUIRED_FIELDS if f not in col_to_field.values()]
            if missing:
                return {
                    "error": f"Kolom wajib tidak ditemukan: {', '.join(missing)}",
                    "status": 400,
                }

            valid_rows: List[dict] = []
            errors: List[dict] = []
            seen_in_file = set()

            for i, raw in enumerate(reader, start=2):  # row 2 = first data row
                row = {}
                for col, field in col_to_field.items():
                    row[field] = (raw.get(col) or "").strip()

                sku = row.get("sku", "")
                # required validation
                missing_vals = [f for f in REQUIRED_FIELDS if not row.get(f)]
                if missing_vals:
                    errors.append({"row": i, "sku": sku or None,
                                   "reason": f"Field kosong: {', '.join(missing_vals)}"})
                    continue
                if len(sku) > 45:
                    errors.append({"row": i, "sku": sku, "reason": "SKU melebihi 45 karakter"})
                    continue
                if sku in seen_in_file:
                    errors.append({"row": i, "sku": sku, "reason": "SKU duplikat di dalam file"})
                    continue

                seen_in_file.add(sku)
                valid_rows.append({
                    "sku": sku,
                    "description": row["description"],
                    "brand": row["brand"],
                    "type": row["type"],
                    "unit": row["unit"],
                    "availablePurchaseType": row.get("availablePurchaseType") or None,
                    "createdBy": user_id,
                    "isDelete": False,
                })

            # skip SKUs already in DB
            existing = await MasterItemRepository.get_existing_skus(
                [r["sku"] for r in valid_rows]
            )
            to_insert = []
            skipped = 0
            for r in valid_rows:
                if r["sku"] in existing:
                    skipped += 1
                else:
                    to_insert.append(r)

            inserted_rows = await MasterItemRepository.bulk_create(to_insert) if to_insert else []
            if inserted_rows:
                index_documents(inserted_rows)

            return {
                "inserted": len(inserted_rows),
                "skipped_duplicates": skipped,
                "failed": len(errors),
                "errors": errors,
            }
        except UnicodeDecodeError:
            return {"error": "File bukan CSV UTF-8 yang valid.", "status": 400}
        except Exception as e:
            log_error(f"Error importing master items CSV: {str(e)}")
            return internal_error()