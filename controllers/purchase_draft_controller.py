from sqlalchemy import func, insert, select, update, delete, or_
from utils.database import database
from models.purchase_draft_model import PurchaseDraft
from models.payment_outgoing_model import PaymentOutgoing
from repository.payment_outgoing_repository import PaymentOutgoingRepository
from models.mutation_model import Mutation
from utils.logger_utils import log_error, log_info
from datetime import datetime
from repository.purchase_repository import PurchaseRepository
from utils.errors import internal_error
from utils.transaksi import atomik

def _ambil(baris, kunci, bawaan=None):
    """
    Baca satu kolom dari hasil query.

    `database.fetch_one` mengembalikan `sqlalchemy.engine.Row`, dan Row
    TIDAK punya `.get()` — memanggilnya melempar AttributeError, bukan
    mengembalikan bawaan. Jadi pembacaannya lewat `keys()`, dan dict tetap
    dilayani karena pemanggilnya kadang sudah mengubahnya jadi dict.
    """
    if baris is None:
        return bawaan
    if isinstance(baris, dict):
        return baris.get(kunci, bawaan)
    try:
        if kunci in baris.keys():
            return baris[kunci]
    except Exception:
        return bawaan
    return bawaan


def _teks(nilai):
    """Nilai untuk riwayat: tanggal jadi `YYYY-MM-DD`, sisanya apa adanya."""
    if nilai is None:
        return None
    if hasattr(nilai, "isoformat"):
        return nilai.isoformat()[:10]
    return nilai


class PurchaseDraftController:
    @staticmethod
    async def create_purchase_draft(purchase_data: dict, userID: int):
        purchase_data["createdBy"] = userID
        purchase_data["createdAt"] = datetime.now()
        purchase_data["isDelete"] = False

        try:
            purchase_id = await PurchaseDraft.create_purchase_draft(purchase_data)
            if not isinstance(purchase_id, int) and "error" in purchase_id:
                log_error(f"Error creating purchase: {purchase_id['error']}")
                return {"error": purchase_id["error"], "status": purchase_id["status"]}
            log_info(f"Purchase draft created successfully with ID: {purchase_id}")
            
            # Jejak audit dicatat SETELAH barisnya benar-benar tersimpan.
            #
            # Draf pembelian sebelumnya tidak meninggalkan jejak sama sekali —
            # dibuat, dikonversi, dan dihapus tanpa satu baris pun di
            # Aktivitas. Padahal draf memuat nilai dokumen dan pemasoknya,
            # dan konversinya melahirkan pembelian yang beneran ditagihkan.
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="purchase_draft",
                entityID=purchase_id,
                action="create",
                userID=userID,
            )

            return {"message": "Purchase draft created successfully", "purchase_draft_id": purchase_id}
        except Exception as e:
            log_error(f"Error creating purchase draft: {str(e)}")
            return internal_error()
    
    @staticmethod
    async def get_purchase_draft(
        page: int,
        pageSize: int,
        isPending: bool,
        isApproved: bool,
        sortBy: str,
        sortByDirection: str,
        keyword: str | None,
        isConverted: bool = False,
        isDeleted: bool = False,
        periodFrom=None,
        periodTo=None,
    ):
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            result = await PurchaseDraft.get_purchase_draft(
                page,
                pageSize,
                isPending,
                isApproved,
                sortBy,
                sortByDirection,
                keyword,
                isConverted,
                isDeleted,
                periodFrom,
                periodTo,
            )
            if "error" in result:
                return {"error": result["error"], "status": result["status"]}
            return result
        except Exception as e:
            log_error(f"Error fetching purchases: {str(e)}")
            return internal_error()         

    @staticmethod
    async def get_purchase_draft_by_id(purchaseID: int):
        result = await PurchaseDraft.get_purchase_draft_by_id(purchaseID)
        if "error" in result:
            return {"error": result["error"], "status": result["status"]}
        
        payments = await PaymentOutgoingRepository.get_payments_by_purchase_id(purchaseID)
        if "error" in payments:
            return {"error": payments["error"], "status": payments["status"]}
        
        response = dict(result)
        
        response["payments"] = payments
        return response
    
    #: Yang boleh diubah setelah draf terbit.
    #:
    #: Hanya angka dan keterangannya — BUKAN pemasok, proyek, atau SPK-nya.
    #: Mengganti itu berarti draf ini sebenarnya draf yang lain, dan
    #: riwayatnya akan menerangkan perubahan yang tidak dapat dibaca siapa
    #: pun ("pemasok: A -> B" pada dokumen yang sama).
    BIDANG_BOLEH_UBAH = (
        "dpp",
        "ppn",
        "pbbkb",
        "description",
        "date",
        "periodStart",
        "periodEnd",
    )

    @staticmethod
    async def ubah_purchase_draft(draft_id: int, muatan: dict, userID: int):
        """
        Ubah nominal/periode draf, DENGAN jejak nilai lamanya.

        Draf lapangan kerap perlu dibetulkan: angka yang salah ketik,
        periode yang meleset. Menghapus lalu membuat ulang menghilangkan
        siapa yang memasukkannya dan kapan — dan itulah satu-satunya jalan
        yang tersedia sebelum ini.

        Yang sudah DIKONVERSI atau DIHAPUS tidak dapat diubah: angkanya
        sudah menjadi tagihan, dan tagihan dibetulkan pada pembeliannya.
        """
        draf = await PurchaseDraft.get_purchase_draft_by_id(draft_id)
        if not draf or _ambil(draf, "error"):
            return {"error": "Draf pembelian tidak ditemukan.", "status": 404}
        if _ambil(draf, "convertedAt"):
            return {
                "error": (
                    "Draf ini sudah dikonversi menjadi pembelian, jadi "
                    "nilainya tidak dapat diubah. Betulkan pada pembeliannya."
                ),
                "status": 409,
            }
        if _ambil(draf, "isDelete"):
            return {"error": "Draf ini sudah dihapus.", "status": 409}

        # Hanya bidang yang BERUBAH yang ditulis — dan hanya itu pula yang
        # masuk riwayat. Menyimpan seluruh bidang membuat riwayat penuh
        # baris "dpp: 1.000.000 -> 1.000.000".
        nilai = {}
        perubahan = {}
        for bidang in PurchaseDraftController.BIDANG_BOLEH_UBAH:
            if bidang not in muatan:
                continue
            baru = muatan[bidang]
            lama = _ambil(draf, bidang)
            if str(lama) == str(baru):
                continue
            nilai[bidang] = baru
            # Kuncinya `from`/`to`, BUKAN `dari`/`ke`.
            #
            # Seluruh aplikasi membaca jejak audit lewat satu komponen, dan
            # komponen itu mencari `from`/`to`. Kunci berbahasa Indonesia
            # tersimpan rapi di basis data tetapi tampil di layar sebagai
            # "— → —": riwayatnya ada, isinya tidak terbaca.
            perubahan[bidang] = {"from": _teks(lama), "to": _teks(baru)}

        if not nilai:
            return {"message": "Tidak ada yang berubah.", "perubahan": {}}

        # Periode diperiksa pada HASIL GABUNGANNYA, bukan pada muatannya.
        #
        # Muatan yang hanya membawa `periodEnd` lolos pemeriksaan di skema —
        # tidak ada `periodStart` di sana untuk dibandingkan — padahal nilai
        # yang tersimpan bisa saja lebih belakangan. Yang menentukan adalah
        # bagaimana barisnya nanti, bukan apa yang dikirim.
        mulai = nilai["periodStart"] if "periodStart" in nilai else _ambil(draf, "periodStart")
        selesai = nilai["periodEnd"] if "periodEnd" in nilai else _ambil(draf, "periodEnd")
        if mulai and selesai and str(selesai) < str(mulai):
            return {
                "error": "Periode selesai tidak boleh mendahului periode mulai.",
                "status": 400,
            }

        terubah = await PurchaseDraft.ubah(draft_id, nilai)
        if not terubah:
            # Kalah cepat: drafnya baru saja dikonversi atau dihapus.
            return {
                "error": (
                    "Draf ini baru saja dikonversi atau dihapus, jadi "
                    "perubahannya tidak disimpan."
                ),
                "status": 409,
            }

        from repository.audit_log_repository import AuditLogRepository

        await AuditLogRepository.record(
            entity="purchase_draft",
            entityID=int(draft_id),
            action="update",
            userID=userID,
            changes=perubahan,
        )

        log_info(f"Purchase draft {draft_id} diubah: {', '.join(perubahan)}")
        return {"message": "Draf pembelian diperbarui.", "perubahan": perubahan}

    @staticmethod
    async def delete_purchase_draft(purchase_draft_id: int, userID: int):
        """
        Hapus draf pembelian.

        Draf yang SUDAH DIKONVERSI tidak dapat dihapus: pembeliannya menunjuk
        balik ke draf ini lewat `purchaseID`, dan menghapusnya membuat
        pembelian yang sudah berjalan kehilangan asal-usulnya — tidak ada
        lagi yang menerangkan dari mana angkanya berasal.

        Yang keliru dibatalkan pada pembeliannya, bukan pada drafnya.
        """
        draf = await PurchaseDraft.get_purchase_draft_by_id(purchase_draft_id)
        # `isinstance(draf, dict)` di sini dahulu membuat penjagaannya tidak
        # pernah menyala: `fetch_one` mengembalikan Row, bukan dict, jadi
        # draf yang sudah dikonversi pun lolos dihapus.
        if _ambil(draf, "convertedAt"):
            return {
                "error": (
                    "Draf ini sudah dikonversi menjadi pembelian dan tidak "
                    "dapat dihapus."
                ),
                "status": 409,
            }

        await PurchaseDraft.delete_purcase_draft(purchase_draft_id, userID)

        from repository.audit_log_repository import AuditLogRepository

        await AuditLogRepository.record(
            entity="purchase_draft",
            entityID=int(purchase_draft_id),
            action="delete",
            userID=userID,
        )

        # Pesan sebelumnya menyebut "converted" pada fungsi yang MENGHAPUS.
        #
        # Yang membaca lognya menyimpulkan drafnya berhasil dikonversi,
        # padahal ia dihapus — dua peristiwa yang berlawanan artinya.
        log_info(f"Purchase draft deleted successfully with ID: {purchase_draft_id}")

        return {
            "message": "Purchase draft deleted successfully",
            "purchase_draft_id": purchase_draft_id,
        }
    
    @staticmethod
    @atomik
    async def convert_purchase_draft(purchase_data: dict, userID: int):
        try:
            print(purchase_data)
            purchase_data["createdBy"] = userID
            purchase_data["createdAt"] = datetime.now()
            purchase_data["isPaid"] = False
            purchase_data["isDelete"] = False
            purchase_draft_id = purchase_data.pop("id")
            
            #Pop supplierName, supplierAddress
            purchase_data.pop("supplierName")
            purchase_data.pop("supplierAddress")
            
            """
            Draft ditandai LEBIH DULU, sebelum pembeliannya dibuat.

            Penandaannya bersyarat pada draft yang belum terkonversi, jadi
            hanya satu permintaan yang berhasil mengubah baris. Bila dua
            permintaan tiba bersamaan — atau seseorang menekan tombol dua
            kali — yang kedua mendapat nol dan berhenti di sini, sebelum
            sempat membuat pembelian kedua.

            Urutan sebaliknya (buat dulu, tandai belakangan) menyisakan celah:
            di antara keduanya, permintaan lain masih bisa lolos dan dua
            pembelian terlanjur ada.
            """
            terkena = await PurchaseDraft.tandai_terkonversi(
                int(purchase_draft_id), None, userID
            )
            if not terkena:
                log_error(f"Draft {purchase_draft_id} sudah dikonversi sebelumnya.")
                return {"error": "DRAFT_ALREADY_CONVERTED", "status": 409}

            purchase_id = await PurchaseRepository.create(purchase_data)
            if not isinstance(purchase_id, int) and "error" in purchase_id:
                # Pembelian gagal dibuat: penandaannya dicabut agar draftnya
                # kembali bisa dikonversi, bukan tertinggal setengah jalan.
                await PurchaseDraft.batalkan_konversi(int(purchase_draft_id))
                log_error(f"Error converting purchase: {purchase_id['error']}")
                return {"error": purchase_id["error"], "status": purchase_id["status"]}

            await PurchaseDraft.catat_purchase_id(int(purchase_draft_id), purchase_id)

            # Konversi dicatat pada KEDUA dokumen.
            #
            # Yang menelusuri sebuah pembelian ingin tahu ia berasal dari draf
            # mana; yang menelusuri draf ingin tahu menjadi pembelian mana.
            # Satu catatan saja membuat salah satu arah itu buntu.
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="purchase_draft",
                entityID=int(purchase_draft_id),
                action="convert",
                userID=userID,
                changes={"purchaseID": purchase_id},
            )
            await AuditLogRepository.record(
                entity="purchases",
                entityID=purchase_id,
                action="create",
                userID=userID,
                changes={"purchaseDraftID": int(purchase_draft_id)},
            )
            await PurchaseDraft.delete_purcase_draft(purchase_draft_id, userID)
            log_info(f"Purchase draft converted successfully with ID: {purchase_id}")
            
            return {"message": "Purchase draft converted successfully", "purchase_id": purchase_id}
        except Exception as e:
            log_error(f"Error converting purchase: {str(e)}")
            return internal_error()