from repository.purchase_repository import PurchaseRepository, PurchaseStatusRepository
from models.payment_outgoing_model import PaymentOutgoing
from repository.payment_outgoing_repository import PaymentOutgoingRepository
from models.mutation_model import Mutation
from repository.reimbursement_repository import ReimbursementRepository
from repository.sales_invoice_repository import SalesInvoiceRepository
from models.purchase_draft_model import PurchaseDraft
from utils.logger_utils import log_error, log_info
from fastapi import HTTPException
from datetime import datetime


def _daftar_atau_kosong(hasil, sebutan: str):
    """
    Hasil satu sumber laporan: daftar apa adanya, atau daftar KOSONG.

    Repositori laporan ini mengembalikan galat 404 ketika tidak menemukan
    baris — bentuk yang masuk akal bagi rute "ambil satu dokumen", tetapi
    keliru bagi laporan: proyek yang belum berbelanja bukan proyek yang tidak
    ditemukan.

    Yang dibedakan STATUSNYA:

        404  tidak ada barisnya       -> daftar kosong, laporan tetap terbit
        400  permintaannya tidak sah  -> dilemparkan
        500  kuerinya gagal           -> dilemparkan

    Galat sungguhan TIDAK boleh menjadi nol. Kueri yang gagal lalu ditampilkan
    sebagai "tidak ada biaya" membuat laporan menyatakan margin penuh atas
    proyek yang justru datanya tidak terbaca — dan tidak ada satu pun tanda
    di layar yang membedakannya dari proyek yang memang belum berbelanja.
    """
    if not isinstance(hasil, dict):
        return hasil or []

    if "error" not in hasil:
        return hasil or []

    if int(hasil.get("status") or 0) == 404:
        return []

    log_error(f"Laporan proyek: {sebutan} gagal dibaca: {hasil['error']}")
    raise HTTPException(status_code=hasil["status"], detail=hasil["error"])


class PurchaseController:

    @staticmethod
    async def belum_dibayar(project_name: str = ""):
        """
        Tagihan pembelian yang belum lunas, beserta ringkasannya.

        Ringkasan disusun di sini, bukan di layar: yang sudah lewat tempo
        menentukan seberapa mendesak, dan menghitungnya di peramban membuat
        angkanya bergantung pada jam mesin yang membukanya.
        """
        data = await PurchaseRepository.belum_dibayar(project_name)
        return {
            "data": data,
            "count": len(data),
            "total": sum(float(x["sisa"] or 0) for x in data),
            "lewatTempo": sum(1 for x in data if x["lewatTempo"]),
            "totalLewatTempo": sum(
                float(x["sisa"] or 0) for x in data if x["lewatTempo"]
            ),
        }
    @staticmethod
    async def create_purchase(purchase_data: dict, userID: int):
        """
        Create a new purchase.
        """
        try:
            purchase_data["createdBy"] = userID
            purchase_data["createdAt"] = datetime.now()
            purchase_data['isDelete'] = False
            purchase_data["isPaid"] = True if purchase_data.get("isInternal") == True else False
            
            lastStatus = purchase_data["lastStatus"]
            lastStatusDescription = purchase_data["lastStatusDescription"]
            
            purchase_id = await PurchaseRepository.create(purchase_data)
            if isinstance(purchase_id, dict) and "error" in purchase_id:
                log_error(f"Error creating purchase: {purchase_id['error']}")
                raise HTTPException(status_code=purchase_id["status"], detail=purchase_id["error"])
            
            log_info(f"Purchase created successfully with ID: {purchase_id}")
            
            # Insert the initial status if the lastStatus is "draft"
            if lastStatus == "draft":
                purchase_status_id = await PurchaseStatusRepository.create({
                    "purchaseID": purchase_id,
                    "status": "draft",
                    "createdAt": purchase_data["createdAt"],
                    "description": lastStatusDescription,
                    "createdBy": userID
                })
                if isinstance(purchase_status_id, dict) and "error" in purchase_status_id:
                    log_error(f"Error creating purchase status: {purchase_status_id['error']}")
                    # Don't fail the whole operation if status creation fails
                    log_info("Purchase created but status creation failed")
            
            return {"message": "Purchase created successfully", "purchase_id": purchase_id}
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error creating purchase: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @staticmethod
    async def check_purchase(invoiceName: str, purchaseOrderName: str):
        """
        Check if a purchase exists with the given invoice name and purchase order name.
        """
        try:
            result = await PurchaseRepository.check_exists(invoiceName, purchaseOrderName)
            if "error" in result:
                log_error(f"Error checking purchase: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error checking purchase: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_purchases(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None):
        """
        Get purchases with pagination and filtering.
        """
        if page < 0:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            result = await PurchaseRepository.get_all(page, pageSize, filterObject, sortBy, sortByDirection, keyword)
            if "error" in result:
                log_error(f"Error fetching purchases: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error fetching purchases: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_purchase_by_id(purchaseID: int):
        """
        Get a purchase by ID.
        """
        try:
            result = await PurchaseRepository.get_by_id(purchaseID)
            payments = await PaymentOutgoingRepository.get_payments_by_purchase_id(purchaseID)
            if "error" in result:
                log_error(f"Error fetching purchase: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            return {
                "purchase": result,
                "payments": payments
            }
        except Exception as e:
            log_error(f"Error fetching purchase: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_purchases_by_purchase_order_name(purchase_order_name: str):
        """
        Get purchases by purchase order name.
        """
        try:
            result = await PurchaseRepository.get_purchases_by_purchase_order_name(purchase_order_name)
            if "error" in result:
                log_error(f"Error fetching purchases: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error fetching purchases: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_payments_by_purchase_id(purchaseID: int):
        """
        Get payments by purchase ID, together with the purchase detail
        (including supplier info) so the client can render the header.
        Returns { "purchase": <detail>, "payments": [...] }.
        """
        try:
            payments = await PaymentOutgoingRepository.get_payments_by_purchase_id(purchaseID)
            if isinstance(payments, dict) and "error" in payments:
                log_error(f"Error fetching payments by purchase ID: {payments['error']}")
                raise HTTPException(status_code=payments["status"], detail=payments["error"])

            purchase = await PurchaseRepository.get_by_id(purchaseID)
            if purchase is None:
                raise HTTPException(status_code=404, detail="Purchase not found")
            if isinstance(purchase, dict) and "error" in purchase:
                raise HTTPException(
                    status_code=purchase.get("status", 500),
                    detail=purchase["error"],
                )

            # The client reads flat fields (supplier_name, supplier_prefix, ...)
            # while get_by_id returns a nested `supplier` object. Provide both.
            purchase = dict(purchase)
            supplier = purchase.get("supplier") or {}
            purchase.setdefault("supplier_name", supplier.get("name"))
            purchase.setdefault("supplier_prefix", supplier.get("prefix"))
            purchase.setdefault("supplier_address", supplier.get("address"))
            purchase.setdefault("supplier_city", supplier.get("city"))
            purchase.setdefault("supplier_province", supplier.get("province"))

            return {
                "purchase": purchase,
                "payments": payments,
            }
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error fetching payments by purchase ID: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_frequent_payment_by_supplier_id(supplierID: int):
        """
        Get frequent payment by supplier ID.
        """
        try:
            result = await PurchaseRepository.get_frequent_payment_by_supplier_id(supplierID)
            if "error" in result:
                log_error(f"Error fetching frequent payment by supplier ID: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            print(result)
            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error fetching frequent payment by supplier ID: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_purchase_report_by_project(projectName: str):
        """
        Get purchase report by project.
        """
        try:
            """
            SUMBER YANG KOSONG BUKAN GALAT.

            Sebelumnya tiap sumber diperiksa `if "error" in ...` lalu
            dilemparkan sebagai HTTPException — termasuk ketika galatnya
            sekadar "No purchases found for this project" berstatus 404.

            Akibatnya seluruh laporan gugur hanya karena SATU sumber kosong.
            Proyek KBPDP punya penjualan Rp 240 juta dan belum punya
            pembelian sama sekali; yang tampil di layar hanya spanduk merah
            "No purchases found", dan penjualannya — satu-satunya angka yang
            ada — ikut hilang.

            Keadaan itu justru biasa, dan ada di kedua arah: pekerjaan yang
            sudah ditagihkan tetapi belum berbelanja, dan pembelian yang
            berjalan sebelum SPK-nya terbit.

            Karena itu tiap sumber yang kosong dijadikan DAFTAR KOSONG, bukan
            galat. Yang benar-benar galat — sambungan putus, kueri gagal,
            status 500 — tetap dilemparkan, sebab menampilkannya sebagai nol
            berarti melaporkan biaya yang lebih kecil daripada sebenarnya.
            """
            purchases = _daftar_atau_kosong(
                await PurchaseRepository.get_by_project(projectName),
                "pembelian",
            )
            reimbursements = _daftar_atau_kosong(
                await ReimbursementRepository.get_by_project(projectName),
                "reimbursement",
            )
            
            # Draft pembelian IKUT dihitung sebagai biaya.
            #
            # Biaya yang belum tercatat justru yang paling berbahaya: tanpanya
            # proyek tampak untung padahal tagihannya belum masuk semua.
            # Aturan yang sama berlaku pada ikhtisar margin seluruh proyek —
            # dua laporan yang memberi angka berbeda untuk proyek yang sama
            # merusak kepercayaan pada dua-duanya.
            drafts = await PurchaseRepository.get_drafts_by_project(projectName)
            if isinstance(drafts, dict) and "error" in drafts:
                log_error(f"Error fetching drafts by project: {drafts['error']}")
                drafts = []

            sales_invoices = _daftar_atau_kosong(
                await SalesInvoiceRepository.get_by_project(projectName),
                "faktur penjualan",
            )

            
            """
            `purchase_drafts` sempat DISEBUT DUA KALI di sini.

            Python memakai yang terakhir, sehingga `drafts` — hasil
            `get_drafts_by_project`, yang sengaja MENGECUALIKAN draft yang
            sudah dikonversi — dibuang diam-diam, dan yang terkirim justru
            `PurchaseDraft.get_by_project` yang menyertakan semuanya.

            Akibatnya draft yang sudah menjadi pembelian terhitung DUA KALI
            sebagai biaya: sekali sebagai pembelian, sekali lagi sebagai
            draftnya. Laporan proyek karena itu menunjukkan biaya lebih besar
            daripada yang sebenarnya, sementara ikhtisar margin seluruh proyek
            — yang memakai aturan benar — menunjukkan angka lain untuk proyek
            yang sama.

            Tidak ada galat: kunci ganda pada dict bukan kesalahan sintaks,
            dan keduanya berbentuk daftar yang sama-sama masuk akal di layar.
            """
            return {
                "purchases": purchases,
                # Draft yang BELUM dikonversi; yang sudah menjadi pembelian
                # tidak ikut, karena biayanya sudah terhitung di sana.
                "purchase_drafts": drafts,
                "reimbursements": reimbursements,
                "sales_invoices": sales_invoices,
            }
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error fetching purchase report by project: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def update_status(purchaseStatus: dict, userID: int):
        """
        Update purchase status.
        """
        try:
            purchase_id = purchaseStatus["id"]

            # Get the purchase first to check if it exists and validate
            purchase = await PurchaseRepository.get_by_id(purchase_id)
            if "error" in purchase:
                log_error(f"Error fetching purchase: {purchase['error']}")
                raise HTTPException(status_code=purchase["status"], detail=purchase["error"])

            if purchase.get("isDelete"):
                return {"error": "Purchase is deleted", "status": 400}
            if purchase.get("lastStatus") == "ready":
                return {"error": "Purchase is already ready", "status": 400}
            
            # Update the purchase status
            result = await PurchaseRepository.update_status(purchase_id, purchaseStatus, userID)
            if "error" in result:
                log_error(f"Error updating purchase status: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            # Create the new status record
            status_result = await PurchaseStatusRepository.create({
                "purchaseID": purchase_id,
                "status": "ready",
                "createdAt": datetime.now(),
                "description": None,
                "createdBy": userID,
            })
            if isinstance(status_result, dict) and "error" in status_result:
                log_error(f"Error creating purchase status: {status_result['error']}")
                # Don't fail the whole operation if status creation fails
                log_info("Purchase updated but status creation failed")
            
            return {"message": "Purchase status updated successfully"}
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error updating purchase status: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @staticmethod
    async def update_purchase(purchaseID: int, data: dict, userID: int, userLevel: int = 0):
        """
        Ubah pembelian.

        Nilai dokumen dikunci bila pembayarannya sudah ada.

        `dpp`, `ppn`, `pbbkb`, `otherValue`, dan `pphPercentage` menentukan
        jumlah yang dibayarkan. Mengubahnya setelah pembayaran disetujui
        membuat angka yang disetujui tidak lagi cocok dengan dokumennya —
        dan tidak ada yang tahu mana yang benar. Persoalannya sama dengan
        penghapusan pembelian berbayar, dan penjaganya pun sama: hanya
        level 4 ke atas yang boleh.

        Bidang lain — nomor faktur, kelengkapan berkas, rekening, keterangan
        — tetap dapat diubah siapa pun yang berhak, karena tidak mengubah
        jumlah yang harus dibayar.
        """
        NILAI = {"dpp", "ppn", "pbbkb", "otherValue", "pphPercentage"}

        try:
            lama = await PurchaseRepository.get_by_id(purchaseID)
            if not lama or (isinstance(lama, dict) and "error" in lama):
                return {"error": "Purchase not found", "status": 404}

            diubah = {
                k for k in NILAI
                if k in (data or {}) and str(data[k]) != str(lama.get(k))
            }
            if diubah:
                jumlah = await PaymentOutgoingRepository.hitung_pembayaran_aktif(
                    purchaseID
                )
                if jumlah != 0 and (userLevel or 0) < 4:
                    log_error(
                        f"Perubahan nilai pembelian {purchaseID} ditolak: "
                        f"{jumlah} pembayaran melekat, level {userLevel}."
                    )
                    return {"error": "PURCHASE_HAS_PAYMENTS", "status": 409}

            return await PurchaseRepository.update(purchaseID, data, userID)
        except Exception as e:
            log_error(f"Error updating purchase {purchaseID}: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    # Bidang meta pembelian LUAR yang boleh disunting lewat jalur ini.
    # Dipisah dari nilai keuangan karena keduanya berbeda penjaga: meta
    # boleh diubah kapan pun, nilai keuangan hanya selama belum ada
    # pembayaran yang melekat.
    #
    # `pphCode` dan `pphTaxObject` masuk kelompok BOLEH, bukan NILAI: keduanya
    # KLASIFIKASI (objek pajak apa), bukan nominal. Mengubahnya tidak menggeser
    # angka yang sudah disetujui — sehingga tetap dapat dibetulkan meski
    # pembayarannya sudah ada. Kasus nyatanya: kode PPh lupa diisi padahal
    # tarifnya 0%. Yang benar-benar mengubah nominal — DPP, PPN, dan TARIF
    # PPh — yang dikunci setelah pembayaran.
    _META_BOLEH = {
        "date", "taxInvoiceName", "invoiceName", "receiptName",
        "pphCode", "pphTaxObject",
    }
    _META_NILAI = {"dpp", "ppn", "pphPercentage"}
    LEVEL_EDIT_META = 5

    @staticmethod
    async def get_purchase_meta(purchaseID: int):
        """
        Detail satu pembelian untuk layar sunting meta, DITAMBAH tanda
        apakah pembayarannya sudah ada.

        Layarnya perlu tahu itu di depan: bila sudah ada pembayaran, kolom
        DPP/PPN/PPh dikunci — mengubahnya membuat nominal yang sudah
        disetujui tidak lagi cocok dengan dokumennya. Tanpa tanda ini
        layar tidak punya cara mengunci kolomnya sebelum orang telanjur
        mengetiknya.
        """
        try:
            purchase = await PurchaseRepository.get_by_id(purchaseID)
            if not purchase or (isinstance(purchase, dict) and "error" in purchase):
                return purchase or {"error": "Purchase not found", "status": 404}

            jumlah = await PaymentOutgoingRepository.hitung_pembayaran_aktif(
                purchaseID
            )
            purchase["hasActivePayment"] = bool(jumlah)
            return purchase
        except Exception as e:
            log_error(f"Error fetching purchase meta {purchaseID}: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update_purchase_meta(
        purchaseID: int, data: dict, userID: int, userLevel: int = 0
    ):
        """
        Sunting META pembelian LUAR — tanggal, nomor faktur pajak, nomor
        invoice, nomor kuitansi; dan DPP/PPN/PPh SELAMA belum ada pembayaran.

        Berbeda dari "Update Internal" yang menyunting seluruh isi dokumen
        internal: jalur ini hanya membetulkan keterangan pembelian LUAR yang
        terlanjur salah ketik — nomor fakturnya keliru, tanggalnya salah —
        tanpa membongkar dokumennya.

        Dua penjaga:

          * HANYA level 5. Pembelian luar adalah dokumen yang menjadi dasar
            pembayaran ke pihak ketiga; membetulkan nomornya dari belakang
            adalah wewenang yang harus dipegang sedikit orang, dan diperiksa
            di server, bukan sekadar disembunyikan tombolnya di layar.

          * Nilai keuangannya (DPP/PPN/PPh) dikunci bila pembayarannya sudah
            ada. Sama seperti pada `update_purchase`: mengubah nominal setelah
            pembayaran disetujui membuat angka yang disetujui tidak lagi cocok
            dengan dokumennya, dan tidak ada yang tahu mana yang benar.
        """
        try:
            if (userLevel or 0) < PurchaseController.LEVEL_EDIT_META:
                log_error(
                    f"Sunting meta pembelian {purchaseID} ditolak: "
                    f"level {userLevel} < {PurchaseController.LEVEL_EDIT_META}."
                )
                return {"error": "FORBIDDEN_LEVEL", "status": 403}

            lama = await PurchaseRepository.get_by_id(purchaseID)
            if not lama or (isinstance(lama, dict) and "error" in lama):
                return {"error": "Purchase not found", "status": 404}

            # Hanya bidang yang memang boleh; sisanya dibuang di sini supaya
            # muatan asing tidak pernah sampai ke repository.
            boleh = PurchaseController._META_BOLEH | PurchaseController._META_NILAI
            bersih = {k: v for k, v in (data or {}).items() if k in boleh}
            if not bersih:
                return {"error": "No editable field supplied.", "status": 400}

            diubah_nilai = {
                k for k in PurchaseController._META_NILAI
                if k in bersih and str(bersih[k]) != str(lama.get(k))
            }
            if diubah_nilai:
                jumlah = await PaymentOutgoingRepository.hitung_pembayaran_aktif(
                    purchaseID
                )
                if jumlah != 0:
                    log_error(
                        f"Perubahan nilai meta pembelian {purchaseID} ditolak: "
                        f"{jumlah} pembayaran melekat."
                    )
                    return {"error": "PURCHASE_HAS_PAYMENTS", "status": 409}

            return await PurchaseRepository.update(purchaseID, bersih, userID)
        except Exception as e:
            log_error(f"Error updating purchase meta {purchaseID}: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def delete_purchase(purchaseID: int, userID: int, userLevel: int = 0):
        """
        Hapus pembelian.

        Menghapus pembelian TIDAK berhenti pada dokumennya: seluruh
        pembayaran yang melekat ikut dihapus dan persetujuannya dicabut.
        Tanpa penjaga, jalur ini membatalkan pembayaran yang hanya boleh
        disetujui level 5 — dan bila uangnya sudah ditransfer, dokumennya
        hilang sementara uangnya sudah keluar.

        Karena itu:
          * Belum ada pembayaran  -> level 3 boleh menghapus.
          * Sudah ada pembayaran  -> hanya level 4 ke atas.

        Yang berlevel di bawah itu harus membatalkan pembayarannya lebih
        dulu, lewat orang yang berwenang, baru pembeliannya dapat dihapus.
        """
        try:
            log_info(f"Attempting to delete purchase with ID: {purchaseID} by user ID: {userID}")
            
            # Check if the purchase exists
            purchase = await PurchaseRepository.get_by_id(purchaseID)
            if "error" in purchase:
                log_error(f"Error fetching purchase: {purchase['error']}")
                raise HTTPException(status_code=purchase["status"], detail=purchase["error"])
            
            if purchase.get("isDelete"):
                return {"error": "Purchase is already deleted", "status": 400}

            jumlah_pembayaran = (
                await PaymentOutgoingRepository.hitung_pembayaran_aktif(purchaseID)
            )
            if jumlah_pembayaran != 0 and (userLevel or 0) < 4:
                log_error(
                    f"Penghapusan pembelian {purchaseID} ditolak: "
                    f"{jumlah_pembayaran} pembayaran melekat, level {userLevel}."
                )
                return {
                    "error": "PURCHASE_HAS_PAYMENTS",
                    "status": 409,
                }

            # Delete the purchase
            result = await PurchaseRepository.delete(purchaseID, userID)
            if "error" in result:
                log_error(f"Error deleting purchase: {result['error']}")
                raise HTTPException(status_code=result["status"], detail=result["error"])
            
            log_info(f"Purchase with ID: {purchaseID} deleted successfully by user ID: {userID}")

            # Delete payments associated with the purchase
            payments_result = await PaymentOutgoingRepository.delete_payment_by_purchase_id(purchaseID, userID)
            if "error" in payments_result:
                log_error(f"Error deleting payments for purchase ID {purchaseID}: {payments_result['error']}")
                # Don't fail the whole operation if payment deletion fails
                log_info(f"Purchase deleted but payment deletion failed for purchase ID {purchaseID}")

            # Get payments history for mutation deletion
            payments_history = await PaymentOutgoingRepository.get_payments_by_purchase_id(purchaseID)
            if not isinstance(payments_history, dict) or "error" not in payments_history:
                log_info(f"Fetching payments history for purchase ID: {purchaseID}")
                
                # Delete mutations associated with the payments
                payment_ids = [payment["id"] for payment in payments_history] if payments_history else []
                if payment_ids:
                    mutation_result = await Mutation.delete_mutations_by_payment_ids(payment_ids)
                    if "error" in mutation_result:
                        log_error(f"Error deleting mutations for payments of purchase ID {purchaseID}: {mutation_result['error']}")
                        # Don't fail the whole operation if mutation deletion fails
                        log_info(f"Purchase deleted but mutation deletion failed for purchase ID {purchaseID}")

            return result
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error deleting purchase: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")