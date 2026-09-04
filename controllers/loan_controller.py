from typing import Dict, Optional
from utils.logger_utils import log_error, log_info
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from datetime import datetime as dt
from repository.loan_repository import LoanRepository
from repository.payment_income_repository import PaymentIncomingRepository
from schemas.loan_schema import TOLERANSI_RUPIAH

class LoanController:
    @staticmethod 
    async def create_loan(loan_data: Dict, user_id: int) -> Dict:
        """Create a new loan."""
        log_info(f"Creating loan with data: {loan_data}")
        try:
            # Add creation metadata
            loan_data["createdAt"] = dt.now()
            loan_data["createdBy"] = user_id
            loan_data["isPaid"] = False

            result = await LoanRepository.create(loan_data)
            if "error" in result:
                log_error(f"Error creating loan: {result['error']}")
                raise HTTPException(status_code=result.get("status", 500), detail=result["error"])

            loan_id = result["loan_id"]
            log_info(f"Loan created successfully with ID: {loan_id}")

            # Otomatis catat dana yang DITERIMA (received) sebagai payment_incoming,
            # terhubung ke loan ini, dengan tanggal sesuai tanggal loan.
            try:
                payment_data = {
                    "date": loan_data["date"],
                    "amount": loan_data.get("received", 0) or 0,
                    "loanID": loan_id,
                    "bankAccountID": loan_data.get("bankAccountID"),
                    "createdBy": user_id,
                    "createdAt": dt.now(),
                    "isApprove": True,
                }
                payment_result = await PaymentIncomingRepository.create(payment_data)
                if "error" in payment_result:
                    # Loan tetap berhasil; kegagalan payment_incoming hanya dicatat.
                    log_error(
                        f"Loan {loan_id} created but auto payment_incoming failed: {payment_result['error']}"
                    )
            except Exception as pay_err:
                log_error(
                    f"Loan {loan_id} created but auto payment_incoming raised: {str(pay_err)}"
                )

            return {"message": "Loan created successfully", "loan_id": loan_id}
        except IntegrityError as e:
            log_error(f"Integrity error: {str(e)}")
            raise HTTPException(status_code=400, detail="Loan already exists.")
        except Exception as e:
            log_error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error.")
    
    @staticmethod
    async def get_loan_by_id(loan_id: int):
        """Get a loan by its ID."""
        try:
            result = await LoanRepository.get_loan_by_id(loan_id)
            if isinstance(result, dict) and "error" in result:
                raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
            return result
        except HTTPException as e:
            raise e
        except Exception as e:
            log_error(f"Unexpected error getting loan by ID: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @staticmethod
    async def get_payments_by_loan_id(loan_id: int):
        """Get active outgoing payments for a specific loan."""
        try:
            result = await LoanRepository.get_payments_by_loan_id(loan_id)
            if isinstance(result, dict) and "error" in result:
                raise HTTPException(status_code=result.get("status", 500), detail=result["error"])
            return result
        except HTTPException as e:
            raise e
        except Exception as e:
            log_error(f"Unexpected error getting payments: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @staticmethod
    async def get_receipts_by_loan_id(loan_id: int):
        """
        Baris `payment_incoming` yang mewakili pencairan pinjaman ini.

        Dipakai layar sunting untuk mengisi rekening penerima ketika
        `loans.bankAccountID` masih kosong. Kolom itu ditambahkan setelah
        sebagian pinjaman tercatat, sehingga baris lama bernilai NULL —
        sementara penerimaannya SELALU punya rekening, karena tanpa itu
        uangnya tidak akan pernah muncul di mutasi bank mana pun. Rekening
        itulah jawaban yang benar atas "sebelumnya masuk ke mana", bukan
        tebakan.

        Gagal membaca dikembalikan sebagai daftar kosong, bukan galat: ini
        hanya bahan pengisi awal, dan menggagalkan seluruh layar sunting
        karena pengisi awalnya tidak terbaca jauh lebih merugikan daripada
        satu kolom yang harus diisi sendiri.
        """
        hasil = await PaymentIncomingRepository.get_by_loan_id(loan_id)
        if isinstance(hasil, dict):
            log_error(
                f"Gagal membaca penerimaan pinjaman {loan_id}: {hasil.get('error')}"
            )
            return []
        return hasil or []

    @staticmethod
    async def get_loans(page: int, pageSize: int, isPaid: bool, isUnpaid: bool, sortBy: str, sortByDirection: str, keyword: Optional[str] = None):
        """Get paginated list of loans with filtering and sorting."""
        try:
            result = await LoanRepository.get_loans(page, pageSize, isPaid, isUnpaid, sortBy, sortByDirection, keyword)
            if "error" in result:
                raise HTTPException(status_code=result["status"], detail=result["error"])
            return result
        except HTTPException as e:
            raise e
        except Exception as e:
            log_error(f"Unexpected error getting loans: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def update_loan(loan_id: int, loan_data: Dict, user_id: int) -> Dict:
        """
        Perbarui data pinjaman.

        Nilai utang boleh diubah, tetapi TIDAK BOLEH turun di bawah jumlah yang
        sudah dibayarkan. Utang 100 juta yang sudah dibayar 80 juta lalu diubah
        menjadi 50 juta berarti pinjaman itu terbayar lebih — dan tidak ada
        tempat di sistem yang mencatat kelebihannya, sehingga selisih 30 juta
        menghilang tanpa jejak.

        Ambangnya memakai toleransi lima rupiah, sama seperti pada persetujuan
        pembayaran: nilai disimpan sebagai desimal sementara pembayaran
        dijumlahkan sebagai pecahan, dan selisih pembulatan beberapa rupiah
        bukan tanda kelebihan bayar.
        """
        try:
            menyentuh_nilai = any(
                loan_data.get(k) is not None for k in ("debt", "received")
            )

            lama_ = None
            if menyentuh_nilai:
                lama_ = await LoanRepository.get_loan_by_id(loan_id)
                if isinstance(lama_, dict) and "error" in lama_:
                    raise HTTPException(status_code=404, detail="Loan not found")

            if loan_data.get("debt") is not None:
                dibayar = await LoanRepository.total_dibayar(loan_id)
                baru_ = float(loan_data["debt"])
                if baru_ + TOLERANSI_RUPIAH < dibayar:
                    log_error(
                        f"Perubahan utang pinjaman {loan_id} ditolak: "
                        f"nilai baru {baru_} di bawah yang sudah dibayar {dibayar}."
                    )
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "LOAN_BELOW_PAID",
                            "message": "Loan value cannot be lower than the amount already paid.",
                            "paid": dibayar,
                        },
                    )

            # Dana diterima tidak boleh melebihi utangnya.
            #
            # Diperiksa atas nilai GABUNGAN — yang baru bila dikirim, yang
            # tersimpan bila tidak. Pembaruan di sini boleh sebagian: layar yang
            # hanya mengubah `received` tidak mengirim `debt` sama sekali, dan
            # membandingkan dua kolom yang salah satunya tidak ada pada muatan
            # berarti aturannya lolos justru pada perubahan yang paling mungkin
            # melanggarnya.
            #
            # Karena itu penjaganya di sini, bukan di skema: skema tidak dapat
            # membaca nilai yang sudah tersimpan.
            if menyentuh_nilai:
                utang_akhir = float(
                    loan_data["debt"]
                    if loan_data.get("debt") is not None
                    else (lama_["debt"] or 0)
                )
                diterima_akhir = float(
                    loan_data["received"]
                    if loan_data.get("received") is not None
                    else (lama_["received"] or 0)
                )
                if diterima_akhir > utang_akhir + TOLERANSI_RUPIAH:
                    log_error(
                        f"Perubahan pinjaman {loan_id} ditolak: dana diterima "
                        f"{diterima_akhir} melebihi utang {utang_akhir}."
                    )
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "LOAN_RECEIVED_ABOVE_DEBT",
                            "message": "Funds received cannot exceed the loan value.",
                            "debt": utang_akhir,
                            "received": diterima_akhir,
                        },
                    )

            result = await LoanRepository.update(loan_id, loan_data, user_id)
            if "error" in result:
                raise HTTPException(status_code=result["status"], detail=result["error"])

            # Status lunas dihitung ulang setiap kali nilainya berubah, ke dua
            # arah: yang tadinya belum lunas bisa menjadi lunas, dan sebaliknya.
            if any(k in loan_data for k in ("debt", "received")):
                await LoanRepository.hitung_ulang_lunas(loan_id, user_id)

            # Penerimaan dananya mengikuti — lihat `_selaraskan_penerimaan`.
            if any(k in loan_data for k in ("received", "bankAccountID")):
                await LoanController._selaraskan_penerimaan(loan_id, user_id)

            return result
        except HTTPException as e:
            raise e
        except Exception as e:
            log_error(f"Unexpected error updating loan: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def _selaraskan_penerimaan(loan_id: int, user_id: int) -> None:
        """
        Samakan baris `payment_incoming` pinjaman dengan nilai terbarunya.

        Mencatat pinjaman membuat DUA baris: pinjamannya sendiri, dan satu
        `payment_incoming` yang mewakili uang masuk ke rekening perusahaan
        (lihat `create_loan`). Baris kedua itulah yang terbaca di mutasi bank
        dan ikut membentuk saldo — `loans.received` tidak dibaca di sana sama
        sekali.

        Sebelum ini, pembaruan hanya menyentuh baris pertama. Nilai pinjaman
        berubah, penerimaannya tidak, dan saldo bank tetap memakai angka
        pertama yang pernah dicatat. Tidak ada galat, tidak ada selisih yang
        muncul di mana pun — kedua angka itu memang tidak pernah dibandingkan.

        Yang diikutkan hanya `amount` dan `bankAccountID`. `date` sengaja
        tidak: tanggal pinjaman tidak dapat disunting, dan bila seseorang
        pernah membetulkan tanggal penerimaannya agar cocok dengan rekening
        koran, menimpanya akan membatalkan koreksi yang disengaja.

        Nilainya diambil dari baris pinjaman yang SUDAH tersimpan, bukan dari
        muatan permintaan: muatannya boleh sebagian, dan yang harus tercermin
        adalah keadaan akhir, bukan potongan yang kebetulan dikirim.

        KETERBATASAN yang diketahui: ini berjalan setelah pinjamannya
        tersimpan, tanpa transaksi yang menaungi keduanya — lapisan repository
        di repo ini tidak menyediakannya, dan controller tidak menyentuh basis
        data langsung. Karena itu kegagalan di sini DILEMPAR, tidak ditelan:
        jawaban berhasil atas penyelarasan yang gagal akan mengulang persis
        cacat yang sedang diperbaiki, hanya lebih sulit ditemukan.
        """
        pinjaman = await LoanRepository.get_loan_by_id(loan_id)
        if isinstance(pinjaman, dict) and "error" in pinjaman:
            raise HTTPException(status_code=404, detail="Loan not found")

        baris = await PaymentIncomingRepository.get_by_loan_id(loan_id)
        if isinstance(baris, dict) and "error" in baris:
            log_error(
                f"Gagal membaca penerimaan pinjaman {loan_id}: {baris.get('error')}"
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "LOAN_RECEIPT_SYNC_FAILED",
                    "message": (
                        "Loan saved, but its incoming payment could not be read."
                    ),
                },
            )

        # Lebih dari satu penerimaan: JANGAN menebak yang mana.
        #
        # Pencatatan otomatis hanya membuat satu, jadi bila ada dua berarti
        # seseorang menambahkannya sendiri — mungkin pencairan bertahap.
        # Memilih salah satu berarti mengubah angka yang bukan haknya, dan
        # membagi rata berarti mengarang. Ditolak dengan sebutan jelas.
        if len(baris) > 1:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "LOAN_RECEIPT_AMBIGUOUS",
                    "message": (
                        "This loan has more than one incoming payment; "
                        "adjust them manually."
                    ),
                    "count": len(baris),
                },
            )

        # `amount` diteruskan apa adanya, sama seperti pada `create_loan`.
        # Yang penting bukan bentuk angkanya, melainkan bahwa nilai `received`
        # yang sama menghasilkan penerimaan yang sama — entah barisnya lahir
        # saat pencatatan atau saat pembaruan.
        nilai = pinjaman.get("received", 0) or 0
        rekening = pinjaman.get("bankAccountID")

        if not baris:
            # Pinjaman lama, dari sebelum pencatatan otomatis ada. Dibuatkan
            # sekarang — tanpa ini, uangnya tidak pernah muncul di mutasi.
            hasil = await PaymentIncomingRepository.create(
                {
                    "date": pinjaman["date"],
                    "amount": nilai,
                    "loanID": loan_id,
                    "bankAccountID": rekening,
                    "createdBy": user_id,
                    "createdAt": dt.now(),
                    "isApprove": True,
                }
            )
        else:
            hasil = await PaymentIncomingRepository.update(
                baris[0]["id"],
                {
                    "amount": nilai,
                    "bankAccountID": rekening,
                    "updatedBy": user_id,
                },
            )

        if isinstance(hasil, dict) and "error" in hasil:
            log_error(
                f"Penerimaan pinjaman {loan_id} gagal diselaraskan: "
                f"{hasil.get('error')}"
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "LOAN_RECEIPT_SYNC_FAILED",
                    "message": (
                        "Loan value saved, but its incoming payment was not "
                        "updated; the bank balance is out of step."
                    ),
                },
            )

    @staticmethod
    async def update_payment_status(loan_id: int, status: bool, user_id: int):
        """Update the payment status of a loan."""
        try:
            result = await LoanRepository.update_payment_status(loan_id, status, user_id)
            if "error" in result:
                raise HTTPException(status_code=result["status"], detail=result["error"])
            return result
        except HTTPException as e:
            raise e
        except Exception as e:
            log_error(f"Unexpected error updating payment status: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")