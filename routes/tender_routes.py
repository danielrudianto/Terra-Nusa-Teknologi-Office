from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from controllers.tender_controller import TenderController
from schemas.tender_schema import (
    TenderCreate,
    TenderPemenang,
    TenderQuoteCreate,
    TenderQuoteUpdate,
    TenderUpdate,
)
from utils.errors import error_detail
from utils.permission import require

router = APIRouter()


def _bereskan(result: dict):
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(
            status_code=result["status"], detail=error_detail(result)
        )
    return result


@router.get("/")
async def daftar_tender(
    current_user: Annotated[dict, Depends(require("tender", "read"))],
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
    status: str = Query(""),
    cari: str = Query(""),
    sortBy: str = Query(None),
    sortByDirection: str = Query("desc"),
):
    """Daftar tender, beserta banyaknya penawaran yang sudah masuk."""
    return _bereskan(
        await TenderController.daftar(
            page, pageSize, status, cari, sortBy, sortByDirection
        )
    )


@router.post("/")
async def buat_tender(
    body: TenderCreate,
    current_user: Annotated[dict, Depends(require("tender", "create"))],
):
    return _bereskan(
        await TenderController.buat(body.model_dump(), current_user["id"])
    )


@router.get("/{tender_id}")
async def ambil_tender(
    tender_id: int,
    current_user: Annotated[dict, Depends(require("tender", "read"))],
):
    """Tender beserta baris permintaan dan seluruh penawarannya."""
    return _bereskan(await TenderController.ambil(tender_id))


@router.put("/{tender_id}")
async def ubah_tender(
    tender_id: int,
    body: TenderUpdate,
    current_user: Annotated[dict, Depends(require("tender", "update"))],
):
    return _bereskan(
        await TenderController.ubah(
            tender_id, body.model_dump(exclude_unset=True), current_user["id"]
        )
    )


@router.post("/{tender_id}/sebarkan")
async def sebarkan_tender(
    tender_id: int,
    current_user: Annotated[dict, Depends(require("tender", "update"))],
):
    """
    Tandai permintaan penawaran sudah disebarkan.

    Penyebarannya lewat WhatsApp dan dikerjakan orang; yang dicatat di sini
    hanya bahwa tender ini sedang menunggu balasan, bukan masih disusun.
    """
    return _bereskan(
        await TenderController.sebarkan(tender_id, current_user["id"])
    )


@router.post("/{tender_id}/batalkan")
async def batalkan_tender(
    tender_id: int,
    current_user: Annotated[dict, Depends(require("tender", "update"))],
):
    return _bereskan(
        await TenderController.batalkan(tender_id, current_user["id"])
    )


@router.delete("/{tender_id}")
async def hapus_tender(
    tender_id: int,
    current_user: Annotated[dict, Depends(require("tender", "delete"))],
):
    return _bereskan(
        await TenderController.hapus(tender_id, current_user["id"])
    )


# ----------------------------------------------------------------------
# Penawaran
# ----------------------------------------------------------------------


@router.post("/{tender_id}/penawaran")
async def tambah_penawaran(
    tender_id: int,
    body: TenderQuoteCreate,
    current_user: Annotated[dict, Depends(require("tender", "update"))],
):
    """
    Catat satu balasan dari pemasok.

    Dijaga izin `tender:update`, bukan `create`: mencatat balasan adalah
    melengkapi tender yang sudah ada, bukan membuat yang baru.
    """
    return _bereskan(
        await TenderController.tambah_penawaran(
            tender_id, body.model_dump(), current_user["id"]
        )
    )


@router.put("/{tender_id}/penawaran/{quote_id}")
async def ubah_penawaran(
    tender_id: int,
    quote_id: int,
    body: TenderQuoteUpdate,
    current_user: Annotated[dict, Depends(require("tender", "update"))],
):
    return _bereskan(
        await TenderController.ubah_penawaran(
            tender_id,
            quote_id,
            body.model_dump(exclude_unset=True),
            current_user["id"],
        )
    )


@router.delete("/{tender_id}/penawaran/{quote_id}")
async def hapus_penawaran(
    tender_id: int,
    quote_id: int,
    current_user: Annotated[dict, Depends(require("tender", "update"))],
):
    return _bereskan(
        await TenderController.hapus_penawaran(
            tender_id, quote_id, current_user["id"]
        )
    )


@router.post("/{tender_id}/pemenang")
async def tetapkan_pemenang(
    tender_id: int,
    body: TenderPemenang,
    current_user: Annotated[dict, Depends(require("tender", "approve"))],
):
    """
    Tetapkan pemenang tender.

    Dijaga izin `tender:approve`, TERPISAH dari `update`: yang mencatat
    penawaran belum tentu yang berhak memutuskan pemenangnya — pemisahan yang
    sama seperti pada pembayaran keluar.
    """
    return _bereskan(
        await TenderController.tetapkan_pemenang(
            tender_id, body.winnerQuoteID, body.winnerReason, current_user["id"]
        )
    )
