from repository.reimbursement_repository import ReimbursementRepository
from models.payment_outgoing_model import PaymentOutgoing
from repository.payment_outgoing_repository import PaymentOutgoingRepository
from schemas.reimbursement_schema import ReimbursementCreate, ReimbursementResponse
from utils.logger_utils import log_error, log_info
from datetime import datetime
from fastapi import HTTPException
from utils.errors import internal_error, app_error, ErrorCode

class ReimbursementController:

    @staticmethod
    async def create_reimbursement(reimbursement_data: dict, userID: int):
        log_info(f"Creating reimbursement with data: {reimbursement_data}")
        try:
            reimbursement_data["createdAt"] = datetime.now()
            reimbursement_data["createdBy"] = userID
            reimbursement_items = reimbursement_data.pop("reimbursementItems", [])
            projectName = reimbursement_data["projectName"]
            reimbursement_data["isPaid"] = False
            reimbursement_data["isDelete"] = False
            reimbursement_data["isApprove"] = False

            count = await ReimbursementRepository.count_by_project_name(projectName)
            if isinstance(count, dict) and "error" in count:
                log_error(f"Error counting reimbursements by project name: {count['error']}")
                return count

            reimbursement_name = f"{count+1:03}-REIM-{projectName}-{reimbursement_data['purchaseType']}"
            reimbursement_data["name"] = reimbursement_name

            reimbursement_id = await ReimbursementRepository.create_reimbursement(reimbursement_data)
            if isinstance(reimbursement_id, dict) and "error" in reimbursement_id:
                log_error(f"Error creating reimbursement: {reimbursement_id['error']}")
                raise HTTPException(status_code=reimbursement_id["status"], detail=reimbursement_id["error"])
            
            log_info(f"Reimbursement created successfully with ID: {reimbursement_id}")
            
            if reimbursement_items:
                reimbursement_items_formatted = []
                for item in reimbursement_items:
                    item["reimbursementID"] = reimbursement_id
                    reimbursement_items_formatted.append(item)
                
                result = await ReimbursementRepository.create_reimbursement_items(reimbursement_items_formatted)
                if "error" in result:
                    log_error(f"Error creating reimbursement items: {result['error']}")
                    # Consider rolling back the reimbursement creation here

            return ReimbursementResponse(
                message="Reimbursement created successfully",
                reimbursementID=reimbursement_id,
                name=reimbursement_name
            )
        except HTTPException:
            # Penolakan yang DISENGAJA diteruskan apa adanya.
            # Tanpa baris ini, `except Exception` di bawah menangkap kembali
            # HTTPException yang baru saja dilempar di dalam `try` yang sama dan
            # mengubahnya menjadi 500 — dan alasan penolakannya hilang sebelum
            # rutenya sempat melihatnya.
            raise
        except Exception as e:
            log_error(f"Error creating reimbursement: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_reimbursements(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None):
        log_info(f"Getting reimbursements for page: {page}")
        result = await ReimbursementRepository.get_reimbursements(page, pageSize, filterObject, sortBy, sortByDirection, keyword)
        if "error" in result:
            log_error(f"Error getting reimbursements: {result['error']}")
            return result
        log_info(f"Reimbursements fetched successfully for page: {page}")
        return result

    @staticmethod
    async def get_reimbursement_by_id(reimbursementID: int):
        log_info(f"Getting reimbursement by ID: {reimbursementID}")
        reimbursement = await ReimbursementRepository.get_reimbursement_by_id(reimbursementID)
        if "error" in reimbursement:
            log_error(f"Error getting reimbursement: {reimbursement['error']}")
            return reimbursement
        
        reimbursement_items = await ReimbursementRepository.get_reimbursement_items_by_reimbursement_id(reimbursementID)
        if "error" in reimbursement_items:
            log_error(f"Error getting reimbursement items: {reimbursement_items['error']}")
            return reimbursement_items
        
        # Note: You'll need to implement PaymentOutgoing repository similarly
        payments = await PaymentOutgoingRepository.get_payments_by_reimbursement_id(reimbursementID)
        if "error" in payments:
            log_error(f"Error getting payments: {payments['error']}")
            return payments
        
        log_info(f"Reimbursement fetched successfully for ID: {reimbursementID}")
        return {
            "reimbursement": reimbursement,
            "reimbursement_items": reimbursement_items,
            "payments": payments
        }

    @staticmethod
    async def approve_reimbursement(reimbursementID: int, userID: int, user_level: int | None = None):
        log_info(f"Approving reimbursement with ID: {reimbursementID}")
        try:
            reimbursement = await ReimbursementRepository.get_reimbursement_by_id(reimbursementID)
            if "error" in reimbursement:
                log_error(f"Error getting reimbursement for approval: {reimbursement['error']}")
                return reimbursement
            
            # Penolakan harus MEMUAT `error`.
            #
            # Rutenya menyaring dengan `if "error" in result`; bentuk lama di
            # sini hanya membawa `message` dan `status`, sehingga penolakannya
            # dikirim apa adanya sebagai **200 OK**. Layar menampilkan
            # "berhasil" untuk tindakan yang tidak mengerjakan apa pun, dan
            # `status: 400` yang menempel di badan jawaban tidak dibaca siapa
            # pun.
            if reimbursement["isApprove"]:
                return app_error(
                    ErrorCode.VALIDATION,
                    "Reimbursement already approved",
                    400,
                )

            if reimbursement["isDelete"]:
                return app_error(
                    ErrorCode.VALIDATION,
                    "Reimbursement is deleted and cannot be approved",
                    400,
                )
        
            result = await ReimbursementRepository.approve_reimbursement_by_id(reimbursementID, userID, user_level)
            if "error" in result:
                log_error(f"Error approving reimbursement: {result['error']}")
                return result
            
            log_info(f"Reimbursement approved successfully for ID: {reimbursementID}")
            return {"message": "Reimbursement approved successfully", "reimbursementID": reimbursementID}
        except Exception as e:
            log_error(f"Error approving reimbursement: {str(e)}")
            return internal_error()

    @staticmethod
    async def reject_reimbursement(reimbursementID: int, userID: int):
        log_info(f"Rejecting reimbursement with ID: {reimbursementID}")
        try:
            reimbursement = await ReimbursementRepository.get_reimbursement_by_id(reimbursementID)
            if "error" in reimbursement:
                log_error(f"Error getting reimbursement for rejection: {reimbursement['error']}")
                return reimbursement
            
            # Lihat keterangan pada `approve_reimbursement`: tanpa `error`,
            # penolakan ini terkirim sebagai 200.
            if reimbursement["isDelete"]:
                return app_error(
                    ErrorCode.VALIDATION, "Reimbursement already deleted", 400
                )
        
            result = await ReimbursementRepository.reject_reimbursement_by_id(reimbursementID, userID)
            if "error" in result:
                log_error(f"Error rejecting reimbursement: {result['error']}")
                return result
            
            log_info(f"Reimbursement rejected successfully for ID: {reimbursementID}")
            return {"message": "Reimbursement rejected successfully", "reimbursementID": reimbursementID}
        except Exception as e:
            log_error(f"Error rejecting reimbursement: {str(e)}")
            return internal_error()