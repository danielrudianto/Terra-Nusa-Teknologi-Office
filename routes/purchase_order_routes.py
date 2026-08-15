from typing import Annotated, Optional
from utils.logger_utils import log_error
from utils.errors import ErrorCode, error_detail
from fastapi import APIRouter, Depends, HTTPException, Query
from controllers.purchase_order_controller import PurchaseOrderController
from schemas.purchase_order_schema import (
    PurchaseOrderCreate, 
    CreatePurchaseOrderResponse, 
    PurchaseOrderResponse,
    PurchaseOrderListResponse,
    PurchaseOrderStatus
)
from utils.auth_utils import get_current_user, User
from utils.permission import require

router = APIRouter()

@router.post("/", response_model=CreatePurchaseOrderResponse)
async def create_purchase_order(
    purchase_order_data: PurchaseOrderCreate,
    current_user: Annotated[User, Depends(require("purchase_order", "create"))]
):
    """
    Create a new purchase order with auto-generated name.
    The name will be generated based on the project name (e.g., 001, 002, 003).
    """
    try:
        user_id = current_user["id"]
        result = await PurchaseOrderController.create_purchase_order(
            purchase_order_data.dict(), 
            user_id
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=result.get("status", 500), 
                detail=error_detail(result)
            )
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"{__name__}: {e}")
        # Galat asli hanya masuk log: isinya dapat memuat nama tabel,
        # nama kolom, atau potongan SQL — keterangan yang berguna bagi
        # penyerang dan tidak berarti bagi penggunanya.
        raise HTTPException(
            status_code=500,
            detail={"code": ErrorCode.INTERNAL, "message": "Internal server error."},
        )
    
@router.get("/rekap")
async def rekap_proyek(
    proyek: str,
    user: Annotated[User, Depends(require("purchase_order", "read"))],
):
    """
    Rekap seluruh purchase order sebuah proyek, untuk diunduh sebagai Excel.

    Ditaruh SEBELUM rute ber-parameter: FastAPI mencocokkan berurutan, dan
    "rekap" akan tertangkap sebagai id dokumen bila di bawah.
    """
    hasil = await PurchaseOrderController.rekap_proyek(proyek)
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(status_code=hasil["status"], detail=error_detail(hasil))
    return hasil


@router.get("/{purchase_order_id}/rantai")
async def get_rantai_dokumen(
    purchase_order_id: int,
    current_user: Annotated[User, Depends(require("purchase_order", "read"))],
):
    """
    Dokumen ini beserta seluruh yang mendahuluinya, urut terbitnya.

    Mencetak adendum harus menyertakan induk dan adendum sebelumnya: adendum
    berisi SELISIH, sehingga dibaca sendirian ia tidak menyatakan keadaan
    pekerjaannya.

    Ditaruh SEBELUM `/{purchase_order_id}` — FastAPI mencocokkan berurutan,
    dan "rantai" akan tertangkap sebagai bagian dari rute itu bila di bawah.

    Tanpa `response_model`: yang dikembalikan daftar dokumen utuh, dan
    penyaring bidang pernah membuang justru yang diperlukan.
    """
    ids = await PurchaseOrderController.rantai_dokumen(purchase_order_id)
    if not ids:
        raise HTTPException(
            status_code=404, detail=error_detail({"error": "Purchase order not found"})
        )

    hasil = []
    for x in ids:
        d = await PurchaseOrderController.get_purchase_order_by_id(x)
        if isinstance(d, dict) and "error" in d:
            continue
        hasil.append(d)
    return hasil


@router.get("/{purchase_order_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order_by_id(
    purchase_order_id: int,
    current_user: Annotated[User, Depends(require("purchase_order", "read"))]
):
    """
    Get a purchase order by its ID.
    """
    try:
        result = await PurchaseOrderController.get_purchase_order_by_id(purchase_order_id)
        
        if "error" in result:
            raise HTTPException(
                status_code=result.get("status", 500), 
                detail=error_detail(result)
            )
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"{__name__}: {e}")
        # Galat asli hanya masuk log: isinya dapat memuat nama tabel,
        # nama kolom, atau potongan SQL — keterangan yang berguna bagi
        # penyerang dan tidak berarti bagi penggunanya.
        raise HTTPException(
            status_code=500,
            detail={"code": ErrorCode.INTERNAL, "message": "Internal server error."},
        )

@router.get("/", response_model=PurchaseOrderListResponse)
async def get_all_purchase_orders(
    current_user: Annotated[User, Depends(require("purchase_order", "read"))],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    keyword: str = Query(None, description="Search by PO number, project, or supplier"),
    sortBy: str = Query(None, description="Sort column: date, value, supplier, project, name, status"),
    sortByDirection: str = Query("desc", description="Sort direction: asc or desc"),
):
    """
    Get all purchase orders with pagination.
    """
    try:
        result = await PurchaseOrderController.get_all_purchase_orders(
            page, page_size, keyword, sortBy, sortByDirection
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=result.get("status", 500), 
                detail=error_detail(result)
            )
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"{__name__}: {e}")
        # Galat asli hanya masuk log: isinya dapat memuat nama tabel,
        # nama kolom, atau potongan SQL — keterangan yang berguna bagi
        # penyerang dan tidak berarti bagi penggunanya.
        raise HTTPException(
            status_code=500,
            detail={"code": ErrorCode.INTERNAL, "message": "Internal server error."},
        )

@router.patch("/{purchase_order_id}/status")
async def update_purchase_order_status(
    purchase_order_id: int,
    status: PurchaseOrderStatus,
    current_user: Annotated[User, Depends(require("purchase_order", "approve"))]
):
    """
    Update the status of a purchase order.
    """
    try:
        user_id = current_user["id"]
        result = await PurchaseOrderController.update_purchase_order_status(
            purchase_order_id, 
            status.value, 
            user_id,
            int(current_user["authenticationLevel"] or 1),
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=result.get("status", 500), 
                detail=error_detail(result)
            )
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"{__name__}: {e}")
        # Galat asli hanya masuk log: isinya dapat memuat nama tabel,
        # nama kolom, atau potongan SQL — keterangan yang berguna bagi
        # penyerang dan tidak berarti bagi penggunanya.
        raise HTTPException(
            status_code=500,
            detail={"code": ErrorCode.INTERNAL, "message": "Internal server error."},
        )

@router.delete("/{purchase_order_id}")
async def delete_purchase_order(
    purchase_order_id: int,
    current_user: Annotated[User, Depends(require("purchase_order", "delete"))]
):
    """
    Soft delete a purchase order.
    """
    try:
        user_id = current_user["id"]
        result = await PurchaseOrderController.delete_purchase_order(purchase_order_id, user_id)
        
        if "error" in result:
            raise HTTPException(
                status_code=result.get("status", 500), 
                detail=error_detail(result)
            )
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"{__name__}: {e}")
        # Galat asli hanya masuk log: isinya dapat memuat nama tabel,
        # nama kolom, atau potongan SQL — keterangan yang berguna bagi
        # penyerang dan tidak berarti bagi penggunanya.
        raise HTTPException(
            status_code=500,
            detail={"code": ErrorCode.INTERNAL, "message": "Internal server error."},
        )


@router.put("/{purchase_order_id}")
async def ubah_purchase_order(
    purchase_order_id: int,
    body: dict,
    current_user: Annotated[User, Depends(require("purchase_order", "update"))],
):
    """
    Ubah purchase order yang BELUM disetujui.

    Dokumen yang sudah disetujui ditolak repository, bukan di sini: itu
    aturan tentang dokumennya, bukan tentang rutenya, dan menaruhnya di satu
    tempat membuat jalur lain tidak dapat melewatinya.

    Nomor revisi dinaikkan setiap kali. Bila draf lama sempat tercetak dan
    sampai ke vendor, nomor itulah yang membedakan mana yang lebih baru.
    """
    user_id = current_user["id"]
    user_level = int(current_user["authenticationLevel"] or 1)

    hasil = await PurchaseOrderController.update_purchase_order(
        purchase_order_id, body, user_id, user_level
    )
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(
            status_code=hasil.get("status", 500), detail=error_detail(hasil)
        )
    return hasil
