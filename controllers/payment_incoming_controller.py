from sqlalchemy import func, insert, select, update, delete, or_
from utils.database import database
from repository.payment_income_repository import PaymentIncomingRepository
from utils.logger_utils import log_error, log_info
from datetime import datetime as dt, date as d
from fastapi import HTTPException
from typing import List
from functools import reduce
from datetime import date
from utils.errors import internal_error
from utils.transaksi import atomik

class PaymentIncomingController:
    @staticmethod
    async def create_payment(payment_data: dict, userID: int):
        """
        Create a new payment in the database.
        
        Args:
            payment_data (dict): The data of the payment to create.
            userID (int): The ID of the user creating the payment.
        
        Returns:
            dict: A success message with the created payment ID.
        """
        payment_data["createdBy"] = userID
        payment_data['createdAt'] = dt.now()
        payment_data['isApprove'] = True
        log_info(f"Creating payment with data: {payment_data}")
        
        try:
            payment = await PaymentIncomingRepository.create(payment_data)
            if "error" in payment:
                log_error(f"Error creating payment: {payment['error']}")
                return {"error": payment["error"], "status": payment.get("status", 500)}
            return payment
        except Exception as e:
            log_error(f"Error creating payment: {str(e)}")
            return internal_error()

    #: Menghapus pembayaran masuk dibatasi level 4 ke atas.
    #:
    #: Mencatatnya level 3 — itu pekerjaan sehari-hari. Membatalkannya bukan:
    #: yang terhapus membuat faktur kembali tampak belum lunas, dan uang yang
    #: sudah masuk rekening tidak lagi terlihat di mana pun. Pemisahannya sama
    #: dengan penghapusan pembelian yang sudah dibayar.
    LEVEL_HAPUS = 4

    @staticmethod
    @atomik
    async def update_payment(payment_id: int, data: dict, user_id: int):
        """
        Betulkan pembayaran masuk yang salah catat.

        Yang dapat dibetulkan hanya REKENING, TANGGAL, dan NOMINAL —
        daftarnya ditegakkan di repository. Fakturnya sendiri tidak dapat
        dipindah: memindahkan pembayaran ke faktur lain melewati seluruh
        penjagaan yang berjalan saat pembayaran dibuat, dan hasilnya dua
        faktur yang dua-duanya salah.

        Nominal dijaga POSITIF di sini, bukan hanya di layar. Nol atau minus
        akan lolos ke pembukuan sebagai penerimaan yang tidak pernah ada.
        """
        try:
            lama = await PaymentIncomingRepository.get_by_id(payment_id)
            if not lama:
                return {"error": "Pembayaran tidak ditemukan.", "status": 404}
            if isinstance(lama, dict) and "error" in lama:
                return lama

            if "amount" in (data or {}):
                try:
                    nominal = float(data["amount"])
                except (TypeError, ValueError):
                    return {"error": "Nominal tidak sah.", "status": 400}
                if nominal <= 0:
                    return {
                        "error": "Nominal pembayaran harus lebih dari nol.",
                        "status": 400,
                    }

            return await PaymentIncomingRepository.update(
                payment_id, data or {}, user_id
            )
        except Exception as e:
            log_error(f"Error updating payment {payment_id}: {str(e)}")
            return internal_error()

    @staticmethod
    @atomik
    async def delete_payment(payment_id: int, user_id: int, user_level: int = 0):
        """
        Hapus pembayaran masuk yang tidak pernah terjadi.

        Dijaga level: lihat `LEVEL_HAPUS`. Penjagaan ini ADA DI SINI, bukan
        hanya di matriks izin — rute lain yang kelak memanggil pembatalan ini
        tetap melewatinya.
        """
        try:
            if (user_level or 0) < PaymentIncomingController.LEVEL_HAPUS:
                log_error(
                    f"Penghapusan pembayaran masuk {payment_id} ditolak: "
                    f"level {user_level}."
                )
                return {
                    "error": (
                        "Penghapusan pembayaran masuk hanya untuk level 4 "
                        "ke atas."
                    ),
                    "status": 403,
                }

            return await PaymentIncomingRepository.soft_delete(
                payment_id, user_id
            )
        except Exception as e:
            log_error(f"Error deleting payment {payment_id}: {str(e)}")
            return internal_error()
