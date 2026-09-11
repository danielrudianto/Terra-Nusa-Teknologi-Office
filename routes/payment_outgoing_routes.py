from typing import Annotated, List
from utils.errors import error_detail
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timedelta, date
from utils.logger_utils import log_error, log_info
from utils.auth_utils import get_current_user
from utils.permission import require
from models.payment_outgoing_model import PaymentOutgoing
from controllers.payment_outgoing_controller import PaymentOutgoingController
from utils.auth_utils import User


router = APIRouter()

@router.post("/mutation")
async def fetch_mutation(
    filterData: dict,
    # `read`, bukan `create`: fungsi ini hanya memanggil
    # `get_mutation_data` dan tidak menulis apa pun. Rutenya POST semata
    # karena penyaringnya dikirim di body.
    user: Annotated[dict, Depends(require("payment_outgoing", "read"))],
):
    """
    Retrieve bank mutation data. Requires a valid token.
    """
    bankAccountID = filterData['bankAccountID']
    page = filterData['page']
    pageSize = filterData['pageSize']
    startDate = filterData['startDate']
    endDate = filterData['endDate']
    
    userID = user["id"]
    result = await PaymentOutgoingController.get_mutation_data(
        startDate,
        endDate,
        page,
        pageSize,
        bankAccountID
    )
    
    if "error" in result:
        log_error(f"Error fetching mutation: {result['error']}")
        raise HTTPException(
            status_code=result.get("status", 500), detail=error_detail(result)
        )

    return result

@router.post("/")
async def create_payment(payment: PaymentOutgoing, user: Annotated[dict, Depends(require("payment_outgoing", "create"))]):
    """
    Create a new payment. Requires a valid token.

    Status dan pesannya diteruskan APA ADANYA dari controller.

    Sebelumnya SETIAP kegagalan dijadikan 500 "Internal server error" — juga
    penolakan yang disengaja dan sudah membawa pesannya sendiri: "dokumen ini
    sudah lunas", "nominal melebihi sisa tagihan". Yang sampai ke pemakai
    hanya "terjadi kesalahan di server, coba lagi nanti", sehingga ia mencoba
    lagi — padahal mencoba lagi tidak akan pernah berhasil, dan yang perlu
    diperbaiki adalah angkanya.

    Lebih buruk lagi ketika dipanggil beruntun: pembuatan beban berhasil,
    pembuatan slipnya ditolak, dan pemakai melihat pesan galat server di atas
    beban yang sebenarnya TERSIMPAN. Ia lalu mengira bebannya gagal dan
    membuatnya sekali lagi.
    """
    userID = user["id"]
    result = await PaymentOutgoingController.create_payment(payment.model_dump(), userID)

    if "error" in result:
        log_error(f"Error creating payment: {result['error']}")
        raise HTTPException(
            status_code=result.get("status", 500), detail=error_detail(result)
        )

    return result

@router.get("/{paymentID}")
async def get_payment_by_id(paymentID: int, user: Annotated[dict, Depends(require("payment_outgoing", "read"))]):
    """
    Get a payment by its ID. Requires a valid token.
    """
    result = await PaymentOutgoingController.get_payment_by_id(paymentID)
    
    # Pembayaran yang tidak ada menjawab 404, bukan 500. Dulu keduanya
    # dijadikan 500, sehingga tautan ke pembayaran yang sudah dihapus
    # terbaca sebagai server rusak.
    if "error" in result:
        log_error(f"Error fetching payment with ID {paymentID}: {result['error']}")
        raise HTTPException(
            status_code=result.get("status", 500), detail=error_detail(result)
        )
    
    return result

@router.get("/")
async def get_payments(
    page: int,
    pageSize: int,
    user: Annotated[dict, Depends(require("payment_outgoing", "read"))],
    sortBy: str = "createdAt",
    sortByDirection: str = "desc",
    isPending: bool = False,
    isApproved: bool = False,
    isRejected: bool = False,
    dateFrom: str = None,
    dateTo: str = None,
    keyword: str = None,
):
    """
    Get a list of payments with pagination, filtering, and sorting.

    `dateFrom`/`dateTo` menyaring rentang tanggal pembayaran; `keyword`
    mencari terutama pada nama lawan transaksi (opponent/pemasok/pegawai),
    ikut nama dokumennya.
    """
    filterObject = {
        "isApproved": isApproved,
        "isPending": isPending,
        "isRejected": isRejected,
        "dateFrom": dateFrom,
        "dateTo": dateTo,
        "keyword": keyword,
    }
    result = await PaymentOutgoingController.get_payments(
        page, pageSize, filterObject, sortBy, sortByDirection
    )
    
    if "error" in result:
        log_error(f"Error fetching payments: {result['error']}")
        raise HTTPException(
            status_code=result.get("status", 500), detail=error_detail(result)
        )
    
    return result

@router.post("/approve/bulk")
async def approve_bulk_payment_status(
    payments: List[int],
    user: Annotated[dict, Depends(require("payment_outgoing", "approve"))]
):
    """
    Approve multiple payments by their IDs. Requires a valid token.
    """
    userID = user["id"]
    # Level diteruskan karena aturan "tidak boleh menyetujui buatan sendiri"
    # dikecualikan untuk pemilik usaha; keputusannya ada di controller.
    # Objek pengguna berupa Record dari pustaka `databases`, yang TIDAK
    # memiliki metode `.get()` — pemanggilannya melempar AttributeError dan
    # persetujuan gagal dengan galat yang tidak menyebut sebabnya.
    #
    # Bila levelnya tidak terbaca, jangan diperlakukan sebagai akses tinggi:
    # yang aman adalah menganggapnya paling rendah.
    userLevel = int(user["authenticationLevel"] or 1)
    result = await PaymentOutgoingController.update_bulk_payment_status(
        payments, "approve", userID, userLevel
    )
    if "error" in result:
        log_error(f"Error approving payments: {result['error']}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    
    return result

@router.post("/reject/bulk")
async def approve_bulk_payment_status(
    payments: List[int],
    user: Annotated[dict, Depends(require("payment_outgoing", "approve"))]
):
    """
    Approve multiple payments by their IDs. Requires a valid token.
    """
    userID = user["id"]
    result = await PaymentOutgoingController.update_bulk_payment_status(payments, "reject", userID)
    
    if "error" in result:
        log_error(f"Error approving payments: {result['error']}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    
    return result

@router.post("/move")
async def move_payment_date(payment: dict,user: Annotated[dict, Depends(require("payment_outgoing", "create"))]):
    #Convert date from yyyy-mm-dd to date object
    date = payment.get("date")
    paymentID = payment.get("id")
    userID = user["id"]
    reason = payment.get("reason") or payment.get("alasan") or ""
    result = await PaymentOutgoingController.move_payment(
        paymentID, date, userID, reason
    )
    
    if "error" in result:
        log_error(f"Error approving payment with ID {paymentID}: {result['error']}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    
    return result

@router.put("/approve/{paymentID}")
async def update_payment_status(
    paymentID: int,
    user: Annotated[dict, Depends(require("payment_outgoing", "approve"))]
):
    """
    Approve a payment by its ID. Requires a valid token.
    """
    userID = user["id"]
    # Objek pengguna berupa Record dari pustaka `databases`, yang TIDAK
    # memiliki metode `.get()` — pemanggilannya melempar AttributeError dan
    # persetujuan gagal dengan galat yang tidak menyebut sebabnya.
    #
    # Bila levelnya tidak terbaca, jangan diperlakukan sebagai akses tinggi:
    # yang aman adalah menganggapnya paling rendah.
    userLevel = int(user["authenticationLevel"] or 1)
    result = await PaymentOutgoingController.update_payment_status(
        paymentID, "approve", userID, userLevel
    )
    
    if "error" in result:
        log_error(f"Error approving payment with ID {paymentID}: {result['error']}")
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    
    return result

@router.put("/reject/{paymentID}")
async def reject_payment_status(
    paymentID: int,
    user: Annotated[dict, Depends(require("payment_outgoing", "approve"))]
):
    """
    Reject a payment by its ID. Requires a valid token.
    """
    userID = user["id"]
    result = await PaymentOutgoingController.update_payment_status(paymentID, "reject", userID)
    
    # Penolakan karena LEVEL menjawab 403, bukan 500 — yang tidak berwenang
    # perlu tahu bahwa ia tidak berwenang, bukan mengira sistemnya sedang
    # bermasalah dan mencoba lagi.
    if "error" in result:
        log_error(f"Error rejecting payment with ID {paymentID}: {result['error']}")
        raise HTTPException(
            status_code=result.get("status", 500), detail=error_detail(result)
        )

    return result


@router.delete("/{paymentID}")
async def delete_payment(
    paymentID: int,
    user: Annotated[dict, Depends(require("payment_outgoing", "approve"))],
):
    """
    Hapus satu pembayaran — HANYA pemilik usaha (level 5).

    Penghapusannya lunak (`isDelete`): barisnya tetap disimpan sebagai jejak
    kas, tetapi tidak lagi dijumlahkan. Status lunas dokumen yang ditagihnya
    dihitung ulang, sehingga yang tadinya lunas bisa kembali belum lunas.

    Batas level ditegakkan di controller — objek pengguna berupa Record yang
    tidak punya `.get()`, dan level yang tidak terbaca dianggap paling rendah.
    """
    userID = user["id"]
    userLevel = int(user["authenticationLevel"] or 1)
    result = await PaymentOutgoingController.delete_payment(
        paymentID, userID, userLevel
    )
    if "error" in result:
        log_error(f"Error deleting payment with ID {paymentID}: {result['error']}")
        raise HTTPException(
            status_code=result.get("status", 500), detail=error_detail(result)
        )
    return result


@router.post("/selaraskan/{jenis}/{dokumen_id}")
async def selaraskan_status_lunas(
    jenis: str,
    dokumen_id: int,
    user: Annotated[User, Depends(require("payment_outgoing", "update"))],
    konfirmasi: bool = False,
):
    """
    Hitung ulang status lunas satu dokumen.

    Dijaga `payment_outgoing:update`, bukan izin dokumennya sendiri: yang
    berubah adalah kesimpulan atas pembayaran, dan yang berwenang menilainya
    adalah yang berwenang atas pembayaran.

    Aman diulang — hasilnya diturunkan dari pembayaran yang tersimpan, bukan
    ditambahkan padanya.

    DUA LANGKAH bila selisihnya kecil. Tanpa `konfirmasi`, selisih di antara
    satu sen dan lima rupiah dijawab `butuh_konfirmasi: true` beserta nilai
    dokumen, jumlah terbayar, dan selisihnya — dan TIDAK ada yang ditulis.
    Panggilan kedua dengan `konfirmasi=true` yang menandainya lunas.

    Jawabannya 200, bukan galat: tidak ada yang keliru pada permintaannya,
    dan yang diperlukan bukan perbaikan melainkan keputusan.
    """
    userID = user["id"]
    hasil = await PaymentOutgoingController.selaraskan_dokumen(
        jenis, dokumen_id, userID, konfirmasi=konfirmasi
    )
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(
            status_code=hasil.get("status", 500), detail=error_detail(hasil)
        )
    return hasil
