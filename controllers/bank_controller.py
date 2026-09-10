from sqlalchemy import insert, select, update, delete, func
from utils.database import database
from repository.bank_account_repository import BankAccount, kolom_dapat_diubah
from models.mutation_model import Mutation
from typing import Dict, List, Optional
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from datetime import datetime as dt, date as d
from utils.redis import r
import json
from models.bank_model import bank_accounts_table
from models.balance_model import Balance
from functools import reduce
from utils.errors import internal_error

class BankController:
    @staticmethod 
    async def create_bank_account(bank_data: Dict, userID: int) -> Dict:
        """
        Create a new bank account in the database.
        
        Args:
            bank_data (Dict): The data of the bank account to create.
        
        Returns:
            Dict: A success message with the created bank account ID.
        """
        log_info(f"Creating bank account with data: {bank_data}")
        try:
            # Create new Bank model

            bank_data["createdAt"] = dt.now()
            bank_data["createdBy"] = userID

            bank = BankAccount(**bank_data)
            result = await bank.create()
            if "error" in result:
                log_error(f"Error creating bank account: {result['error']}")
                raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
            
            bank_id = result['bank_account_id']            

            # Add to redis
            # CATATAN: cache ini tidak lagi menjadi sumber banks/all.
            # Tidak ada yang membacanya; update_bank_account pun tidak
            # pernah menyegarkannya. Jangan dijadikan sumber data lagi.
            r.rpush("bank_account", json.dumps({
                "id": bank_id,
                "bankAccountNumber": bank_data["bankAccountNumber"],
                "bankAccountName": bank_data["bankAccountName"],
                "bankName": bank_data["bankName"],
            }))

            # Rekening bank dicatat: nomor rekening menentukan ke mana uang
            # perusahaan berpindah, dan perubahannya perlu dapat ditelusuri
            # sampai ke orangnya.
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="bank_accounts",
                entityID=int(bank_id),
                action="create",
                userID=userID,
            )

            log_info(f"Bank account created successfully with ID: {result['bank_account_id']}")
            return {"message": "Bank account created successfully", "bank_id": result['bank_account_id']}
        except IntegrityError as e:
            log_error(f"Integrity error: {str(e)}")
            raise HTTPException(status_code=400, detail="Bank account already exists.")
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")

    @staticmethod
    async def get_bank_accounts(
        page: int,
        sortBy: str = None,
        sortByDirection: str = "asc",
        keyword: str | None = None,
        keadaan: str = "aktif",
    ) -> Dict:
        """
        Retrieve all bank accounts from the database.
        
        Args:
            page (int, sortBy: str = None, sortByDirection: str = "asc"): The page number for pagination.
        
        Returns:
            Dict: A list of all bank accounts.
        """
        log_info(f"Getting all bank accounts for page: {page}")
        if page < 1:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            result = await BankAccount.get_banks(
                page=page,
                pageSize=10,
                sortBy=sortBy,
                sortByDirection=sortByDirection,
                keyword=keyword,
                keadaan=keadaan,
            )
            if "error" in result:
                log_error(f"Error retrieving bank accounts: {result['error']}")
                return {"error": result["error"], "status": result["status"]}
            
            ids = [item['id'] if isinstance(item, dict) else item.id for item in result['data']]
            balances = await Balance.fetch_by_bank_account_ids(ids)
            if isinstance(balances, dict) and "error" in balances:
                log_error(f"Error retrieving balances: {balances['error']}")
                return {"error": balances["error"], "status": balances["status"]}
            
            return {
                "data": result["data"],
                "count": result["count"],
                "balances": balances
            }
        except Exception as e:
            log_error(f"Error retrieving bank accounts: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_all_bank_accounts() -> List[Dict]:
        """
        Seluruh rekening bank untuk dropdown dan pemilih rekening kalender.

        Sumbernya basis data, BUKAN Redis.

        Cache "bank_account" tidak pernah diperbarui oleh update_bank_account,
        sehingga isinya hanya benar sampai rekening itu pertama kali dibuat.
        Setiap kolom baru — dan setiap perubahan nama rekening — tidak pernah
        sampai ke pemanggil. Kegagalannya sunyi: bidangnya hilang, bukan
        error, jadi tampilannya tampak bekerja padahal nilainya tidak pernah
        terbaca.
        """
        log_info("Getting all bank accounts")
        try:
            query = select(bank_accounts_table).order_by(
                bank_accounts_table.c.isDelete,
                bank_accounts_table.c.bankAccountNumber,
            )
            rows = await database.fetch_all(query)
            return [
                {
                    "id": row.id,
                    "bankName": row.bankName,
                    "bankAccountName": row.bankAccountName,
                    "bankAccountNumber": row.bankAccountNumber,
                    "isDelete": bool(row.isDelete),
                    "excludeFromCalendar": bool(
                        getattr(row, "excludeFromCalendar", False)
                    ),
                }
                for row in rows
            ]
        except Exception as e:
            log_error(f"Error retrieving all bank accounts: {str(e)}")
            return internal_error()
    @staticmethod
    async def get_bank_account_by_id(bank_id: int) -> Optional[Dict]:
        """
        Retrieve a bank account by its ID.
        
        Args:
            bank_id (int): The ID of the bank account to retrieve.
        
        Returns:
            Optional[Dict]: The bank account data if found, otherwise None.
        """
        log_info(f"Getting bank account with ID: {bank_id}")
        try:
            bank_account = await BankAccount.get_bank_account_by_id(bank_id)
            return bank_account
        except Exception as e:
            log_error(f"Error retrieving bank account with ID {bank_id}: {str(e)}")
            return None
        
    @staticmethod
    async def update_bank_account(bank_data: Dict, bank_id: int, userID: int) -> Dict:
        """
        Update a bank account in the database.
        
        Args:
            bank_data (Dict): The updated data of the bank account.
            bank_id (int): The ID of the bank account to update.
        
        Returns:
            Dict: A success message if the update was successful.
        """
        log_info(f"Updating bank account with ID: {bank_id} and data: {bank_data}")
        #Check if there is any bank account with the same number but different ID
        
        
        try:
            existing_account_query = (
                select(bank_accounts_table)
                .where(bank_accounts_table.c.bankAccountNumber == bank_data["bankAccountNumber"])
                .where(bank_accounts_table.c.id != bank_id)
            )
            existing_account = await database.fetch_one(existing_account_query)
            if existing_account:
                log_error(f"Bank account with the same number already exists: {bank_data['bankAccountNumber']}")
                return {"error": "Bank account with the same number already exists", "status": 404}
        
            # Muatan klien disaring menjadi kolom tabel yang boleh diubah.
            #
            # Sebelumnya `bank_data.copy()` diteruskan apa adanya, termasuk
            # `balance` — bidang turunan pada model Pydantic yang bukan kolom
            # tabel. Akibatnya SETIAP penyuntingan rekening gagal dengan
            # "Unconsumed column names: balance", dan pemakai hanya melihat
            # "Terjadi kesalahan pada sistem".
            update_fields = kolom_dapat_diubah(bank_data)
            update_fields["updatedAt"] = dt.now()
            update_fields["updatedBy"] = userID

            query = (
                update(bank_accounts_table)
                .where(bank_accounts_table.c.id == bank_id)
                .values(**update_fields)
            )
            # Keadaan SEBELUM diubah diambil lebih dulu.
            #
            # Setelah `execute`, nilai lamanya sudah tertimpa dan tidak dapat
            # direkam lagi — jejak yang hanya menyebut "diubah" tanpa
            # menyebut dari apa menjadi apa tidak menjawab pertanyaan yang
            # membuatnya diperlukan.
            sebelum = await database.fetch_one(
                select(bank_accounts_table).where(
                    bank_accounts_table.c.id == bank_id
                )
            )

            result = await database.execute(query)
            if result == 0:  # Check if any rows were affected
                return {"error": "Update failed or bank account not found", "status": 404}
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="bank_accounts",
                entityID=int(bank_id),
                action="update",
                userID=userID,
                changes=AuditLogRepository.diff(
                    dict(sebelum) if sebelum else {}, bank_data
                ),
            )

            return {"message": "Bank account updated successfully"}
        except Exception as e:
            log_error(f"Error updating bank account with ID {bank_id}: {str(e)}")
            return internal_error()
        
    @staticmethod
    async def delete_bank_account(bankID: int, userID: int):
        """
        Delete a bank account from the database.
        
        Args:
            bankID (int): The ID of the bank account to delete.
            userID (int): The ID of the user performing the deletion.
        
        Returns:
            Dict: A success message if the deletion was successful.
        """
        log_info(f"Deleting bank account with ID: {bankID}")
        try:
            # Rekening bersaldo TIDAK boleh dihapus.
            #
            # Saldo adalah uang yang masih ada. Menghapus rekeningnya
            # mengeluarkannya dari saldo gabungan dan dari kalender kas,
            # sementara uangnya tetap di bank — perencanaan kas lalu terbaca
            # lebih ketat daripada keadaan sebenarnya, dan tidak ada satu pun
            # layar yang menunjukkan ke mana perginya.
            #
            # Rekening yang benar-benar selesai dipakai selalu dapat
            # dikosongkan lebih dulu lewat pemindahan antar rekening; yang
            # ditahan di sini hanya rekening yang masih berisi.
            saldo = await Balance.fetch_by_bank_account_ids([bankID])
            if isinstance(saldo, dict) and "error" in saldo:
                # Gagal membaca saldo diperlakukan seolah saldonya ADA:
                # menolak penghapusan yang mungkin sah lebih ringan
                # akibatnya daripada menghilangkan rekening berisi.
                log_error(f"Gagal membaca saldo rekening {bankID} sebelum dihapus")
                return {"error": "BANK_BALANCE_UNKNOWN", "status": 409}

            nilai = next(
                (float(x["balance"] or 0) for x in saldo if x["id"] == bankID), 0.0
            )
            # Setengah rupiah: pembulatan DECIMAL tidak pernah menghasilkan
            # selisih sebesar itu, tetapi nol yang tersimpan sebagai 0,0000
            # juga tidak boleh dibaca sebagai bersaldo.
            if abs(nilai) > 0.5:
                log_error(
                    f"Penghapusan rekening {bankID} ditolak: saldo {nilai}"
                )
                return {"error": "BANK_HAS_BALANCE", "status": 409}

            result = await BankAccount.delete_bank_account(bankID, userID)
            if "error" in result:
                return {"error": result["error"], "status": result["detail"]}
            
            # CATATAN: cache ini tidak lagi menjadi sumber banks/all.
            # Tidak ada yang membacanya; update_bank_account pun tidak
            # pernah menyegarkannya. Jangan dijadikan sumber data lagi.
            bank_accounts = r.lrange("bank_account", 0, -1)
            for index, account in enumerate(bank_accounts):
                account_data = json.loads(account)
                if account_data["id"] == bankID:
                    # Save change the status
                    account_data["isDelete"] = True
                    r.lset("bank_account", index, json.dumps(account_data))
                    break
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="bank_accounts",
                entityID=int(bankID),
                action="delete",
                userID=userID,
            )

            return {"message": "Bank account deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting bank account with ID {bankID}: {str(e)}")
            return internal_error()
        
    @staticmethod
    async def fetch_mutation(bankAccountID: int, page: int, pageSize: int, startDate: str, endDate: str):
        sdate = dt.strptime(startDate, "%Y-%m-%d")
        edate = dt.strptime(endDate, "%Y-%m-%d")
        try:
            result = await Mutation.fetch_mutation(bankAccountID, page, pageSize, sdate, edate)
            return result
        except Exception as e:
            log_error(f"Error retrieving bank account mutation: {str(e)}")
            return None
        
    @staticmethod
    async def download_mutation(bankAccountID: int, month: int, year: int):
        try:
            result = await Mutation.download_mutation(bankAccountID, month, year)
            return result
        except Exception as e:
            log_error(f"Error retrieving bank account mutation: {str(e)}")
            return internal_error()
        