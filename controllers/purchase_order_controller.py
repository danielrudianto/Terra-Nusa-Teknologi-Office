from typing import Dict
from utils.errors import ErrorCode, app_error
from datetime import datetime as dt
from utils.logger_utils import log_info, log_error
from repository.purchase_order_repository import PurchaseOrderRepository
from repository.purchase_order_item_repository import PurchaseOrderItemRepository
from repository.supplier_repository import SupplierRepository
from utils.errors import internal_error


class PurchaseOrderController:
    #: Jenis PO yang dokumennya terbit sebagai SURAT PERINTAH KERJA.
    #:
    #: Sisanya terbit sebagai PURCHASE ORDER. Daftar ini disalin dari helper
    #: cetak di frontend — di sanalah judul dokumennya ditentukan, dan bila
    #: kelak berubah, ubah keduanya bersamaan.
    JENIS_SPK = {"A", "B", "D", "H", "6.4.1", "6.4.2", "6.5.2", "5.1.12"}

    #: Kolom yang TIDAK BOLEH berbeda antara adendum dan induknya.
    #:
    #: Adendum adalah perubahan atas perjanjian yang sudah ada — bukan
    #: perjanjian baru. Mengganti pemasok berarti menagih pihak lain atas
    #: dokumen bernomor sama; mengganti proyek memindahkan biayanya ke
    #: pembukuan proyek yang berbeda tanpa jejak.
    KOLOM_TERKUNCI_ADENDUM = ("supplierID", "projectName", "purchaseType")

    #: Isian `customData` yang menentukan JENIS DOKUMEN yang terbit.
    #:
    #: Keempatnya memutuskan apakah dokumennya PURCHASE ORDER atau SURAT
    #: PERINTAH KERJA. Mengubahnya pada adendum membuat `013-ADD1-PO-...`
    #: terbit di atas lembar berjudul SURAT PERINTAH KERJA — nomor dan
    #: judulnya bertentangan pada satu lembar yang sama.
    #:
    #: Daftar ini harus sama dengan yang dibaca `_awalan_dokumen`; bila ada
    #: penentu baru di sana, tambahkan di sini juga.
    CUSTOM_TERKUNCI_ADENDUM = (
        "materialType",
        "maintenanceMode",
        "marketingMode",
        "recruitmentMode",
    )

    @staticmethod
    async def pemeriksaan(
        supplier_id: int,
        project_name: str = "",
        dpp: float = 0,
        item_id: int = 0,
        price: float = 0,
        kecuali_id: int = 0,
    ) -> dict:
        """
        Peringatan sebelum dokumen dibuat: harga melompat, dan kemungkinan
        duplikat.

        Keduanya PERINGATAN, bukan penghalang. Harga memang dapat melompat —
        pemasok mengganti spesifikasi, kurs bergerak, atau justru catatan
        lama yang keliru. Yang diperlukan bukan menghentikan orang,
        melainkan menyodorkan angka pembandingnya beserta nomor dokumennya,
        sehingga dapat diperiksa saat itu juga.
        """
        hasil = {"harga": None, "duplikat": None}

        if item_id and price and float(price) > 0:
            terakhir = await PurchaseOrderRepository.harga_terakhir(
                item_id, supplier_id
            )
            if terakhir and terakhir["price"] > 0:
                rasio = float(price) / terakhir["price"]

                # Ambang 1,5x naik dan 0,6x turun.
                #
                # Dipilih dari bentuk kesalahan yang benar-benar terjadi:
                # kelebihan satu nol menghasilkan 10x, kekurangan satu nol
                # 0,1x, dan digit tertukar sekitar 4x. Gerak harga yang wajar
                # — bahkan kenaikan besi yang tajam — jarang melampaui 30%.
                #
                # Ambang yang lebih ketat akan berbunyi pada kenaikan biasa,
                # dan peringatan yang sering keliru berhenti dibaca.
                if rasio >= 1.5 or rasio <= 0.6:
                    hasil["harga"] = {
                        "sebelumnya": terakhir["price"],
                        "sekarang": float(price),
                        "rasio": round(rasio, 2),
                        "tanggal": terakhir["date"],
                        "nomor": terakhir["number"],
                        "satuan": terakhir["unit"],
                    }

        if project_name and dpp:
            hasil["duplikat"] = await PurchaseOrderRepository.kemungkinan_duplikat(
                supplier_id, project_name, float(dpp), kecuali_id or None
            )

        return hasil

    @staticmethod
    def _periksa_kunci_adendum(induk: dict, baru: dict) -> list[str]:
        """
        Bandingkan adendum dengan induknya; kembalikan daftar yang berbeda.

        Dikembalikan sebagai daftar, bukan melempar pada perbedaan pertama,
        supaya yang mengisi melihat seluruhnya sekaligus.
        """
        import json

        masalah: list[str] = []

        for kolom in PurchaseOrderController.KOLOM_TERKUNCI_ADENDUM:
            lama = induk.get(kolom)
            kini = baru.get(kolom)
            if kini is None:
                continue
            if str(lama or "") != str(kini or ""):
                masalah.append(f"{kolom}: {lama!r} -> {kini!r}")

        def _custom(x):
            c = x.get("customData")
            if isinstance(c, str):
                try:
                    return json.loads(c or "{}")
                except Exception:
                    return {}
            return c or {}

        c_induk, c_baru = _custom(induk), _custom(baru)
        for kunci in PurchaseOrderController.CUSTOM_TERKUNCI_ADENDUM:
            if kunci not in c_baru:
                continue
            if str(c_induk.get(kunci) or "") != str(c_baru.get(kunci) or ""):
                masalah.append(
                    f"{kunci}: {c_induk.get(kunci)!r} -> {c_baru.get(kunci)!r}"
                )
        return masalah

    #: Kode jenis yang punya VARIAN, dipetakan ke jenis dasarnya.
    #:
    #: PO-H mengirim "H1" (badan usaha) atau "H2" (perorangan) — perbedaan
    #: yang hanya menentukan isi dokumennya, bukan jenis dokumennya. Keduanya
    #: tetap SURAT PERINTAH KERJA.
    #:
    #: Tanpa pemetaan ini, "H1" tidak pernah cocok dengan "H" pada daftar di
    #: atas, sehingga subkontraktor bernomor `013-PO-MICZ-H1` padahal
    #: lembarnya berjudul SURAT PERINTAH KERJA. Akar yang sama pernah
    #: membuat pratinjaunya tampil tanpa satu klausul pun.
    VARIAN_JENIS = {"H1": "H", "H2": "H"}

    #: Jenis material PO-F yang berupa JASA PENGUJIAN.
    #:
    #: Ketiganya menghasilkan SURAT PERINTAH KERJA, bukan PURCHASE ORDER:
    #: yang dibeli bukan barang melainkan pekerjaan menguji, dan yang
    #: diterima kembali adalah laporannya.
    #:
    #: Daftar ini SATU-SATUNYA sumbernya. Sebelumnya ditulis langsung pada
    #: `_awalan_dokumen`, dan ketika "ujitanah" ditambahkan di layar, daftar
    #: di sini tidak ikut — sehingga SPK uji tanah bernomor `040-PO-...`
    #: padahal lembarnya berjudul SURAT PERINTAH KERJA.
    MATERIAL_JASA_UJI = ("ujitekan", "ujibesi", "ujitanah")

    @staticmethod
    def _awalan_dokumen(purchase_type: str, custom: dict | None = None) -> str:
        """
        Awalan nomor mengikuti dokumen yang benar-benar terbit.

        Sebelumnya seluruh jenis memakai "SPK", sehingga pembelian beton
        tercetak berjudul PURCHASE ORDER tetapi bernomor `013-SPK-MICZ-F` —
        vendor menerima dua sebutan berbeda pada satu lembar yang sama.

        PO-F adalah satu-satunya jenis yang bentuknya bergantung isian:
        jasa pengujian menghasilkan SPK, pengadaan materialnya PO. Karena
        itu `customData` ikut dibaca di sini.
        """
        jenis = (purchase_type or "").strip()
        # Varian diringkas ke jenis dasarnya sebelum apa pun diperiksa.
        jenis = PurchaseOrderController.VARIAN_JENIS.get(jenis, jenis)
        c = custom or {}

        # Empat jenis bentuknya bergantung isian, bukan kodenya saja.
        # Nama kunci penentunya berbeda-beda karena tiap formulir menamainya
        # sendiri; menebak satu nama membuat tiga lainnya salah diam-diam.
        if jenis == "F":
            return (
                "SPK"
                if c.get("materialType")
                in PurchaseOrderController.MATERIAL_JASA_UJI
                else "PO"
            )
        if jenis == "5.1.2":
            return "PO" if c.get("maintenanceMode") == "barang" else "SPK"
        if jenis in ("6.3.1", "6.3.2"):
            return "PO" if c.get("marketingMode") == "barang" else "SPK"
        if jenis == "6.5.1":
            return "PO" if c.get("recruitmentMode") == "kuota" else "SPK"

        return "SPK" if jenis in PurchaseOrderController.JENIS_SPK else "PO"

    @staticmethod
    async def generate_purchase_order_name(
        project_code: str = "",
        purchase_type: str = "",
        custom: dict | None = None,
        parent_number: int | None = None,
        addendum_number: int | None = None,
    ) -> tuple[str, int]:
        """
        Nomor dokumen dengan urutan berjalan per proyek.

        Format: {seq:03d}-{PO|SPK}-{projectCode}-{purchaseType}
        contoh: 025-PO-MICZ-G, 013-SPK-MICZ-A

        Awalannya mengikuti dokumen yang terbit, tetapi DERETNYA tetap satu
        per proyek. Memisahkan deret per jenis akan menghasilkan dua dokumen
        bernomor 001 pada proyek yang sama, dan itu menyulitkan saat dokumen
        dicari kembali.

        Urutan dihitung per proyek: proyek baru mulai dari 001 lagi, dan
        menambah dokumen di satu proyek tidak menggeser nomor proyek lain.

        Nomor lama yang sudah terbit tidak ikut berubah — nomor adalah
        identitas dokumen, dan mengubahnya memutus jejak ke faktur maupun
        pembayaran yang sudah mengacu padanya.
        """
        try:
            if parent_number is not None:
                # Urutan diambil dari induknya; tidak menambah deret proyek.
                number = parent_number
            elif project_code:
                number = await PurchaseOrderRepository.get_next_project_sequence(
                    project_code
                )
            else:
                # tanpa kode proyek, jatuh kembali ke urutan global
                number = (
                    await PurchaseOrderRepository.get_global_purchase_order_count()
                ) + 1
            seq = f"{number:03d}"
            awalan = PurchaseOrderController._awalan_dokumen(purchase_type, custom)

            # Adendum memakai URUTAN INDUKNYA, bukan urutan baru.
            #
            # `013-PO-BPBP-F` beradendum menjadi `013-ADD1-PO-BPBP-F`:
            # urutan, kode proyek, dan jenisnya tetap sama — itulah yang
            # menjadikannya adendum atas dokumen tersebut, bukan dokumen
            # lain yang berdiri sendiri.
            #
            # Diselipkan pada posisi KEDUA, sesuai dokumen yang sudah
            # terbit selama ini.
            sisipan = f"ADD{addendum_number}-" if addendum_number else ""

            if project_code and purchase_type:
                name = f"{seq}-{sisipan}{awalan}-{project_code}-{purchase_type}"
            elif project_code:
                name = f"{seq}-{sisipan}{awalan}-{project_code}"
            else:
                name = f"{seq}-{sisipan}".rstrip("-")
            log_info(
                f"Generated purchase order number '{name}' for project '{project_code}'"
            )
            return name, number
        except Exception as e:
            log_error(f"Error generating purchase order name: {str(e)}")
            return str(int(dt.now().timestamp()))[-3:], 0

    @staticmethod
    async def rantai_dokumen(purchase_order_id: int) -> list[int]:
        """Id induk beserta adendum sampai dokumen ini, urut terbitnya."""
        return await PurchaseOrderRepository.rantai_dokumen(purchase_order_id)

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

            # ---- adendum ----
            #
            # Bila ada induknya, urutan dan nomor adendumnya diambil dari
            # sana. Nomor adendum dihitung DI SINI, bukan dikirim layar:
            # dua orang yang membuat adendum bersamaan atas induk yang sama
            # akan menghasilkan nomor yang sama bila layar yang menentukan.
            parent_id = purchase_order_data.get("parentPurchaseOrderID")
            parent_number = None
            addendum_number = None
            if parent_id:
                induk = await PurchaseOrderRepository.get_by_id(parent_id)
                if not induk:
                    return {"error": "Parent purchase order not found", "status": 404}
                parent_number = induk.get("number")
                if parent_number is None:
                    # Dokumen lama yang nomornya diketik manual tidak punya
                    # urutan; adendumnya tidak dapat dibentuk otomatis.
                    return {
                        "error": "Parent purchase order has no sequence number",
                        "status": 400,
                    }
                # Pemasok, proyek, jenis, dan penentu jenis dokumen tidak
                # boleh berbeda dari induknya.
                #
                # Adendum adalah perubahan atas perjanjian yang SUDAH ADA.
                # Mengganti pemasok berarti menagih pihak lain atas dokumen
                # bernomor sama; mengganti proyek memindahkan biayanya ke
                # pembukuan proyek berbeda tanpa jejak; dan mengganti jenis
                # materialnya membuat nomor ber-"PO" terbit di atas lembar
                # berjudul SURAT PERINTAH KERJA.
                beda = PurchaseOrderController._periksa_kunci_adendum(
                    dict(induk), purchase_order_data
                )
                if beda:
                    return {
                        "error": (
                            "Adendum tidak boleh mengubah: " + "; ".join(beda)
                        ),
                        "status": 400,
                    }

                addendum_number = (
                    await PurchaseOrderRepository.next_addendum_number(parent_id)
                )
                purchase_order_data["addendumNumber"] = addendum_number

                # Pengurangan tidak boleh melampaui yang tersisa.
                #
                # Tanpa ini, adendum yang mengurangi 150 dari pekerjaan
                # bersisa 100 menghasilkan volume minus lima puluh —
                # pekerjaan bernilai negatif, yang tidak berarti apa pun
                # dan merusak laporan margin tanpa memunculkan galat.
                #
                # Diperiksa DI SINI, bukan hanya di layar: layar dapat
                # dilewati, dan yang menjaga keutuhan angka harus yang
                # paling dekat dengan tempat menyimpannya.
                masalah = await PurchaseOrderRepository.periksa_pengurangan(
                    parent_id, items
                )
                if masalah:
                    return {
                        "error": "Pengurangan melebihi sisa: " + "; ".join(masalah),
                        "status": 400,
                    }

            # use client-provided PO number, otherwise auto-generate
            if explicit_name:
                purchase_order_name = explicit_name
                purchase_order_number = None
            else:
                (
                    purchase_order_name,
                    purchase_order_number,
                ) = await PurchaseOrderController.generate_purchase_order_name(
                    project_code or "",
                    purchase_order_data.get("purchaseType", ""),
                    purchase_order_data.get("customData") or {},
                    parent_number,
                    addendum_number,
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
            return internal_error()

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
            return internal_error()

    @staticmethod
    async def rekap_proyek(project_name: str):
        """
        Rekap seluruh purchase order sebuah proyek, untuk diunduh sebagai
        Excel.

        Melewati controller seperti seluruh rute lain di berkas ini, bukan
        memanggil repository langsung: rutenya tidak mengimpor repository, dan
        menyimpang dari polanya membuat satu jalur yang berbeda sendiri tanpa
        alasan.
        """
        return await PurchaseOrderRepository.rekap_proyek(project_name)

    @staticmethod
    async def get_all_purchase_orders(
        page: int = 1,
        page_size: int = 10,
        keyword: str = None,
        sortBy: str = None,
        sortByDirection: str = "desc",
        status: str = None,
        purchase_type: str = None,
        project_name: str = None,
        date_from: str = None,
        date_to: str = None,
    ):
        try:
            result = await PurchaseOrderRepository.get_all(
                page,
                page_size,
                keyword,
                sortBy,
                sortByDirection,
                status=status,
                purchase_type=purchase_type,
                project_name=project_name,
                date_from=date_from,
                date_to=date_to,
            )
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error fetching purchase orders: {str(e)}")
            return internal_error()

    @staticmethod
    async def update_purchase_order(
        purchase_order_id: int,
        fields: Dict,
        user_id: int,
        user_level: int = 1,
        user_name: str | None = None,
    ):
        """
        Ubah purchase order yang belum disetujui.

        Yang boleh: PEMBUATNYA sendiri, atau level 4 ke atas.

        Pembuatnya diikutkan dengan sengaja — yang salah ketik biasanya yang
        mengisi, dan memaksanya meminta tolong orang lain membuat orang
        menghindari koreksi. Yang dijaga bukan siapa yang mengetik, melainkan
        bahwa dokumennya belum disetujui.
        """
        try:
            dokumen = await PurchaseOrderRepository.get_by_id(purchase_order_id)
            if not dokumen or (isinstance(dokumen, dict) and "error" in dokumen):
                return app_error(
                    ErrorCode.NOT_FOUND, "Purchase order tidak ditemukan.", 404
                )

            pembuat = None
            try:
                pembuat = dokumen["createdBy"]
            except (KeyError, TypeError):
                pembuat = getattr(dokumen, "createdBy", None)

            boleh = (
                pembuat is not None and int(pembuat) == int(user_id)
            ) or int(user_level or 1) >= 4
            if not boleh:
                return app_error(
                    ErrorCode.FORBIDDEN,
                    "Hanya pembuat dokumen atau level 4 ke atas yang dapat "
                    "mengubah purchase order ini.",
                    403,
                )

            # drop None values so we only update provided fields
            clean = {k: v for k, v in fields.items() if v is not None}
            status = clean.get("status")
            if status is not None and hasattr(status, "value"):
                clean["status"] = status.value
            # `user_id` dan `user_name` DITERUSKAN.
            #
            # Tanpa keduanya jejak audit tercatat tanpa pelaku — barisnya ada,
            # tetapi kolom siapa-yang-mengubah kosong, dan itu tidak terlihat
            # sebagai kesalahan pada siapa pun yang membacanya.
            result = await PurchaseOrderRepository.update(
                purchase_order_id, clean, user_id, user_name
            )
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error updating purchase order: {str(e)}")
            return internal_error()

    @staticmethod
    async def set_checked(
        purchase_order_id: int,
        checked: bool,
        user_id: int,
        user_level: int | None = None,
        departments: set | None = None,
    ):
        """Tandai dokumen sudah atau belum diperiksa."""
        return await PurchaseOrderRepository.set_checked(
            purchase_order_id, checked, user_id, user_level, departments
        )

    @staticmethod
    async def update_purchase_order_status(
        purchase_order_id: int, status: str, user_id: int,
        user_level: int | None = None,
    ):
        try:
            result = await PurchaseOrderRepository.update_status(
                purchase_order_id, status, user_id, user_level
            )
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error updating purchase order status: {str(e)}")
            return internal_error()

    @staticmethod
    async def approve_purchase_order(purchase_order_id: int, user_id: int, user_level: int | None = None):
        try:
            result = await PurchaseOrderRepository.approve(purchase_order_id, user_id, user_level)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error approving purchase order: {str(e)}")
            return internal_error()

    @staticmethod
    async def delete_purchase_order(purchase_order_id: int, user_id: int):
        try:
            result = await PurchaseOrderRepository.soft_delete(purchase_order_id, user_id)
            if "error" in result:
                return {"error": result["error"], "status": result.get("status", 500)}
            return result
        except Exception as e:
            log_error(f"Error deleting purchase order: {str(e)}")
            return internal_error()