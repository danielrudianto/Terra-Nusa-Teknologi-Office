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
            
            return {"message": "Purchase draft created successfully", "purchase_draft_id": purchase_id}
        except Exception as e:
            log_error(f"Error creating purchase draft: {str(e)}")
            return internal_error()
    
    @staticmethod
    async def get_purchase_draft(page: int, pageSize: int, isPending: bool, isApproved: bool, sortBy: str, sortByDirection: str, keyword: str | None):
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            result = await PurchaseDraft.get_purchase_draft(page, pageSize, isPending, isApproved, sortBy, sortByDirection, keyword)
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
    
    @staticmethod
    async def delete_purchase_draft(purchase_draft_id: int, userID: int):
        await PurchaseDraft.delete_purcase_draft(purchase_draft_id, userID)
        log_info(f"Purchase draft converted successfully with ID: {purchase_draft_id}")
        
        return {"message": "Purchase draft converted successfully", "purchase_id": purchase_draft_id}
    
    @staticmethod
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
            await PurchaseDraft.delete_purcase_draft(purchase_draft_id, userID)
            log_info(f"Purchase draft converted successfully with ID: {purchase_id}")
            
            return {"message": "Purchase draft converted successfully", "purchase_id": purchase_id}
        except Exception as e:
            log_error(f"Error converting purchase: {str(e)}")
            return internal_error()