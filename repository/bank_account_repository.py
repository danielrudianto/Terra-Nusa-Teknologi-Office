from pydantic import BaseModel, Field
from typing import Optional, Annotated
from utils.database import database
from sqlalchemy.exc import IntegrityError
from datetime import date as d, datetime as dt
from models.bank_model import bank_accounts_table
from models.payment_outgoing_model import payments_outgoing_table
from models.payment_incoming_model import payment_incoming_table
from utils.logger_utils import log_error
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Date, Float, select, func
from utils.errors import internal_error

# Kolom yang TIDAK boleh ikut diubah dari muatan klien.
#
# `BankAccount.__init__` mengisi createdAt dengan dt.now() bila kosong, dan
# rute mengirim createdBy apa adanya dari klien (kerap None). Tanpa saringan
# ini, penyuntingan pertama yang berhasil akan menimpa tanggal pembuatan dan
# menghapus pencatat aslinya — persis jejak yang audit log dibuat untuk
# menjaganya.
KOLOM_TIDAK_DIUBAH = {"id", "createdAt", "createdBy"}


def kolom_dapat_diubah(bank_data: dict) -> dict:
    """
    Saring muatan klien menjadi kolom tabel yang boleh diubah.

    Rute `PUT /banks/{id}` mengirim `BankAccount.model_dump()`, dan model
    Pydantic itu memuat `balance` — bidang TURUNAN yang dihitung dari mutasi,
    bukan kolom `bank_accounts`. Meneruskannya apa adanya ke `.values()`
    membuat SQLAlchemy melempar "Unconsumed column names: balance", galatnya
    ketangkap `except Exception`, dan yang sampai ke pemakai hanya "Terjadi
    kesalahan pada sistem" tanpa menyebut sebab.

    Menyaring di sini, bukan di controller, karena berkas inilah yang tahu
    kolom tabelnya. Bidang turunan berikutnya yang ditambahkan ke model
    Pydantic tidak akan mematahkan penyuntingan lagi.
    """
    kolom = {c.name for c in bank_accounts_table.columns}
    return {
        k: v
        for k, v in bank_data.items()
        if k in kolom and k not in KOLOM_TIDAK_DIUBAH
    }


# Define the Purchase model
class BankAccount(BaseModel):
    id: Optional[int] = Field(default=None, title="ID of the bank account", ge=1)
    bankName: str  # Name of the bank
    bankAccountName: str  # Name of the bank account
    bankAccountNumber: str  # Bank account number
    createdBy: int | None = None  # ID of the user who created the bank account
    createdAt: Optional[dt] = None
    updatedBy: Optional[int] = None  # ID of the user who last updated the bank account
    updatedAt: Optional[dt] = None  # Last update date of the bank account
    deletedBy: Optional[int] = None  # ID of the user who deleted the bank account
    deletedAt: Optional[dt] = None  # Deletion date of the bank account
    isDelete: bool = False  # Flag to indicate if the purchase is deleted
    excludeFromCalendar: bool = False  # Dikecualikan dari saldo gabungan dan kalender
    balance: float | None = None

    # Initialize the model with default values
    def __init__(self, **data):
        super().__init__(**data)
        if self.createdAt is None:
            self.createdAt = dt.now()

    async def create(self):
        """
        Create a new bank account in the database.
        
        Returns:
            Dict: A success message with the created bank account ID.
        """
        try:
            query = bank_accounts_table.insert().values(
                bankName=self.bankName,
                bankAccountName=self.bankAccountName,
                bankAccountNumber=self.bankAccountNumber,
                createdBy=self.createdBy,
                createdAt=self.createdAt,
                updatedBy=self.updatedBy,
                updatedAt=self.updatedAt,
                deletedBy=self.deletedBy,
                deletedAt=self.deletedAt,
                isDelete=self.isDelete,
                excludeFromCalendar=self.excludeFromCalendar,
            )
            result = await database.execute(query)
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="bank_accounts",
                entityID=result,
                action="create",
            )
            return {"message": "Bank account created successfully", "bank_account_id": result}
        except IntegrityError as e:
            # Handle integrity errors, such as unique constraint violations
            log_error(f"Integrity error while creating bank account: {str(e.orig)}")
            return {"error": str(e.orig), "status": 400}
        except Exception as e:
            # Handle any other exceptions
            log_error(f"Unexpected error while creating bank account: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_banks(
        page: int = 1,
        pageSize: int = 10,
        sortBy: str = None,
        sortByDirection: str = "asc",
    ) -> dict:
        """
        Retrieve all bank accounts from the database with pagination.
        
        Args:
            page (int): The page number for pagination.
            pageSize (int): The number of items per page.
        
        Returns:
            Dict: A dictionary containing the list of bank accounts and pagination info.
        """
        # Aliases for tables
        ba = bank_accounts_table

        offset = (page - 1) * pageSize
        # Kolom yang boleh dipakai mengurutkan; daftar putih mencegah nama
        # kolom sembarang ikut masuk ke query.
        SORTABLE = {
            "bankName": bank_accounts_table.c.bankName,
            "bankAccountName": bank_accounts_table.c.bankAccountName,
            "bankAccountNumber": bank_accounts_table.c.bankAccountNumber,
        }
        _kolom = SORTABLE.get(sortBy, bank_accounts_table.c.bankAccountNumber)
        _urut = (
            _kolom.desc()
            if str(sortByDirection).lower() == "desc"
            else _kolom.asc()
        )

        # Rekening terhapus tetap ditaruh di bawah, apa pun kolom pengurutnya.
        query = (
            bank_accounts_table.select()
            .order_by(bank_accounts_table.c.isDelete, _urut)
            .limit(pageSize)
            .offset(offset)
        )
        try:
            query = (
                select(
                    ba
                )
                .select_from(
                    ba
                )
                .order_by(ba.c.isDelete, ba.c.bankAccountNumber)
                .limit(pageSize)
                .offset(offset)
            )

            result = await database.fetch_all(query)
            response = []
            for row in result:
                response.append(
                    BankAccount(
                        id=row.id,
                        bankName=row.bankName,
                        bankAccountName=row.bankAccountName,
                        bankAccountNumber=row.bankAccountNumber,
                        createdBy=row.createdBy,
                        createdAt=row.createdAt,
                        updatedBy=row.updatedBy,
                        updatedAt=row.updatedAt,
                        deletedBy=row.deletedBy,
                        deletedAt=row.deletedAt,
                        isDelete=row.isDelete,
                        excludeFromCalendar=bool(getattr(row, "excludeFromCalendar", False)),
                        balance=0
                    )
                )

            count_query = select(func.count()).select_from(bank_accounts_table).where(bank_accounts_table.c.isDelete == False)
            count = await database.fetch_val(count_query)

            return {"data": response, "count": count if count is not None else 0}
        except Exception as e:
            log_error(f"Error fetching bank accounts: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_bank_account_by_id(id: int) -> dict:
        """
        Retrieve a bank account by its ID.
        
        Args:
            id (int): The ID of the bank account.
        
        Returns:
            BankAccount: The bank account details or None if not found.
        """
        query = bank_accounts_table.select().where(
            bank_accounts_table.c.id == id
        )

        try:
            row = await database.fetch_one(query)
            if row:
                return BankAccount(
                    id=row.id,
                    bankName=row.bankName,
                    bankAccountName=row.bankAccountName,
                    bankAccountNumber=row.bankAccountNumber,
                    createdBy=row.createdBy,
                    createdAt=row.createdAt,
                    updatedBy=row.updatedBy,
                    updatedAt=row.updatedAt,
                    deletedBy=row.deletedBy,
                    deletedAt=row.deletedAt,
                    isDelete=row.isDelete,
                    excludeFromCalendar=bool(getattr(row, "excludeFromCalendar", False)),
                )
            else:
                return None
        except Exception as e:
            log_error(f"Error fetching bank account by ID {id}: {str(e)}")
            return internal_error()
    
    @staticmethod
    async def get_bank_accounts_by_ids(ids: list[int] | None):
        """
        Fetch bank account IDs
        """
        if ids is None:
            query = bank_accounts_table.select().where(bank_accounts_table.c.isDelete == False)
        else:
            query = bank_accounts_table.select().where(bank_accounts_table.c.id.in_(ids))
        
        result = await database.fetch_all(query)
        response = []
        for row in result:
            response.append(
                BankAccount(
                    id=row.id,
                    bankName=row.bankName,
                    bankAccountName=row.bankAccountName,
                    bankAccountNumber=row.bankAccountNumber,
                    createdBy=row.createdBy,
                    createdAt=row.createdAt,
                    updatedBy=row.updatedBy,
                    updatedAt=row.updatedAt,
                    deletedBy=row.deletedBy,
                    deletedAt=row.deletedAt,
                    isDelete=row.isDelete,
                    excludeFromCalendar=bool(getattr(row, "excludeFromCalendar", False)),
                )
            )
        return response
        
    @staticmethod
    async def delete_bank_account(id: int, deletedBy: int) -> dict:
        """
        Delete a bank account by its ID.
        
        Args:
            id (int): The ID of the bank account to delete.
            deletedBy (int): The ID of the user who is deleting the bank account.
        
        Returns:
            Dict: A success message or an error message if not found.
        """
        query = bank_accounts_table.update().where(
            bank_accounts_table.c.id == id
        ).values(
            isDelete=True,
            deletedBy=deletedBy,
            deletedAt=dt.now()
        )

        try:
            result = await database.execute(query)
            if result:
                return {"message": "Bank account deleted successfully."}
            else:
                return {"error": "Bank account not found.", "status": 404}
        except Exception as e:
            log_error(f"Error deleting bank account with ID {id}: {str(e)}")
            return internal_error()
