"""
Rute Certificate of Payment.

Divisi TIDAK diambil dari objek pengguna: yang dikembalikan `require()` tidak
memuatnya sama sekali, dan membacanya dari sana selalu menghasilkan kosong —
setiap orang engineering akan ditolak tanpa sebab yang terlihat. Ia dibaca
dari basis data lewat `_departments`, sama seperti pada purchase order.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from controllers.certificate_of_payment_controller import (
    CertificateOfPaymentController,
)
from schemas.certificate_of_payment_schema import (
    CoPAdjustmentSet,
    CoPCreate,
    CoPUpdate,
)
from utils.auth_utils import User
from utils.errors import ErrorCode, error_detail
from utils.logger_utils import log_error
from utils.permission import _departments, require

router = APIRouter()


def _level(user) -> int:
    return int(user["authenticationLevel"] or 1)


def _lempar_bila_galat(hasil):
    if isinstance(hasil, dict) and "error" in hasil:
        raise HTTPException(
            status_code=hasil.get("status", 500), detail=error_detail(hasil)
        )
    return hasil


@router.get("/spk")
async def daftar_spk(
    current_user: Annotated[User, Depends(require("certificate_of_payment", "read"))],
    projectName: Optional[str] = None,
    keyword: Optional[str] = None,
):
    """
    SPK yang dapat dijadikan dasar CoP.

    Layar TIDAK menyaring sendiri jenis dokumennya: purchase order pembelian
    tidak boleh sampai ke daftar pilihan sama sekali. Menyaringnya di layar
    berarti aturan yang sama ditulis dua kali, dan yang tertinggal saat
    jenisnya bertambah tidak menimbulkan galat apa pun.
    """
    return _lempar_bila_galat(
        await CertificateOfPaymentController.spk_kandidat(
            projectName, keyword, _level(current_user)
        )
    )


@router.get("/pagu/{purchase_order_id}")
async def pagu_spk(
    purchase_order_id: int,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "read"))],
):
    """
    Baris pekerjaan SPK beserta sisa pagunya.

    Inilah yang dibaca layar pengisi CoP: pekerjaan apa saja yang ada pada
    SPK, berapa yang sudah disertifikasi, dan berapa yang masih boleh.
    Nilai rupiahnya disaring mengikuti level pembacanya.
    """
    return _lempar_bila_galat(
        await CertificateOfPaymentController.pagu_spk(
            purchase_order_id, _level(current_user)
        )
    )


@router.get("/")
async def daftar_cop(
    current_user: Annotated[User, Depends(require("certificate_of_payment", "read"))],
    purchaseOrderID: Optional[int] = None,
    projectName: Optional[str] = None,
    createdBy: Optional[int] = None,
    page: int = Query(0, ge=0),
    pageSize: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None,
    sortBy: Optional[str] = None,
    sortDir: Optional[str] = None,
    keadaan: Optional[str] = None,
):
    """
    Daftar CoP.

    `keadaan` disaring di SERVER — draft, diperiksa, atau disetujui. Dipakai
    keping penyaring pada layar daftar dan penghitung pada beranda ponsel;
    keduanya membaca `total` dari jawaban yang sama, sehingga angka dan isi
    layarnya tidak dapat berselisih.
    """
    return _lempar_bila_galat(
        await CertificateOfPaymentController.get_all(
            purchase_order_id=purchaseOrderID,
            project_name=projectName,
            created_by=createdBy,
            page=page,
            page_size=pageSize,
            user_level=_level(current_user),
            keyword=keyword,
            sort_by=sortBy,
            sort_dir=sortDir,
            keadaan=keadaan,
        )
    )


@router.get("/siap-tagih")
async def cop_siap_tagih(
    current_user: Annotated[User, Depends(require("certificate_of_payment", "read"))],
    keyword: Optional[str] = None,
    purchaseOrderID: Optional[int] = None,
):
    """
    CoP yang sudah disetujui dan belum ditagihkan.

    Dibaca formulir pembelian untuk memilih dasar tagihannya, dan — dengan
    `purchaseOrderID` — untuk memperingatkan bahwa SPK yang barusan dipilih
    masih menyisakan CoP yang belum ditagihkan. Satu jalan keluar untuk
    kedua maksud itu: peringatan yang dijawab kueri lain akan menyebut CoP
    yang tidak ada di daftar pilihannya begitu aturannya bergeser sedikit.
    """
    return _lempar_bila_galat(
        await CertificateOfPaymentController.siap_tagih(
            keyword, _level(current_user), purchase_order_id=purchaseOrderID
        )
    )


@router.get("/periode-tindih")
async def periode_tindih(
    current_user: Annotated[User, Depends(require("certificate_of_payment", "read"))],
    purchaseOrderID: int,
    periodStart: str,
    periodEnd: str,
    kecualiCopID: Optional[int] = None,
):
    """
    CoP lain atas SPK yang sama yang periodenya bertindih.

    Didaftarkan SEBELUM `/{cop_id}`: rute berparameter menangkap apa pun
    yang menyerupainya, dan "periode-tindih" akan terbaca sebagai sebuah id
    lalu ditolak sebagai bukan angka.
    """
    return _lempar_bila_galat(
        await CertificateOfPaymentController.periode_bertindih(
            purchaseOrderID, periodStart, periodEnd, kecualiCopID
        )
    )


@router.get("/{cop_id}")
async def detail_cop(
    cop_id: int,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "read"))],
):
    return _lempar_bila_galat(
        await CertificateOfPaymentController.get_by_id(cop_id, _level(current_user))
    )


@router.post("/")
async def buat_cop(
    data: CoPCreate,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "create"))],
):
    """Buat certificate of payment atas sebuah SPK."""
    try:
        divisi = await _departments(current_user["id"])
        return _lempar_bila_galat(
            await CertificateOfPaymentController.create(
                data.model_dump(),
                current_user["id"],
                _level(current_user),
                divisi,
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"{__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"code": ErrorCode.INTERNAL, "message": "Internal server error."},
        )


@router.put("/{cop_id}")
async def ubah_cop(
    cop_id: int,
    data: CoPUpdate,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "update"))],
):
    divisi = await _departments(current_user["id"])
    return _lempar_bila_galat(
        await CertificateOfPaymentController.update(
            cop_id,
            data.model_dump(exclude_unset=True),
            current_user["id"],
            _level(current_user),
            divisi,
        )
    )


@router.patch("/{cop_id}/checked")
async def periksa_cop(
    cop_id: int,
    checked: bool,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "update"))],
):
    """
    Tandai CoP sudah/belum diperiksa.

    Dijaga izin `update`, bukan `approve`: memeriksa bukan menyetujui, dan
    menyamakan izinnya berarti setiap pemeriksa otomatis dapat menerbitkan
    dokumen tanpa seorang pun memutuskannya.
    """
    divisi = await _departments(current_user["id"])
    return _lempar_bila_galat(
        await CertificateOfPaymentController.set_checked(
            cop_id, checked, current_user["id"], _level(current_user), divisi
        )
    )


def _pdf(isi: bytes, nama: str) -> Response:
    """
    Kirim sebagai berkas yang LANGSUNG diunduh.

    `attachment`, bukan `inline`: dokumen ini dibawa ke pembukuan dan
    ditandatangani, jadi yang menekan tombol memang menghendaki berkasnya —
    bukan pratinjau di dalam tab yang harus disimpan sekali lagi.
    """
    return Response(
        content=isi,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nama}"'},
    )


def _nama_berkas(nama_cop: str, akhiran: str) -> str:
    """Nomor dokumen memuat garis miring; itu memisah folder pada unduhan."""
    aman = (nama_cop or "CoP").replace("/", "-").replace("\\", "-")
    return f"{aman}{akhiran}.pdf"


@router.get("/{cop_id}/pdf")
async def unduh_pdf(
    cop_id: int,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "read"))],
):
    """
    Certificate of Payment beserta lampiran BAP — satu berkas, dua orientasi.

    Level 1 ditolak controller: lembar ini memuat harga satuan dan nilai
    kontrak, dan orang lapangan memang tidak pernah menerimanya.
    """
    from services.pdf_service import CoPDocumentService

    data = _lempar_bila_galat(
        await CertificateOfPaymentController.data_cetak(
            cop_id, _level(current_user), sertakan_cop=True
        )
    )
    return _pdf(
        CoPDocumentService.render(data, sertakan_bap=True),
        _nama_berkas(data["cop"]["name"], ""),
    )


@router.get("/{cop_id}/bap-pdf")
async def unduh_bap(
    cop_id: int,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "read"))],
):
    """
    Berita Acara Pemeriksaan saja — seluruhnya lanskap.

    `sertakan_cop=False`: BAP boleh diunduh SEBELUM diperiksa. Ia menyatakan
    volume yang terlaksana, bukan nilai yang dibayar — dan justru inilah
    lembar yang dibawa ke lapangan untuk diperiksa lebih dahulu.
    """
    from services.pdf_service import CoPDocumentService

    data = _lempar_bila_galat(
        await CertificateOfPaymentController.data_cetak(
            cop_id, _level(current_user), sertakan_cop=False
        )
    )
    return _pdf(
        CoPDocumentService.render_bap(data),
        _nama_berkas(data["cop"]["name"], "-BAP"),
    )


@router.put("/{cop_id}/adjustments")
async def set_penyesuaian(
    cop_id: int,
    data: CoPAdjustmentSet,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "update"))],
):
    """
    Ganti seluruh potongan & tambahan CoP.

    Dijaga izin `update`, tetapi wewenang sebenarnya diperiksa controller:
    hanya pemeriksa (engineering level 2 ke atas) yang boleh — orang lapangan
    tidak pernah menerima angka rupiahnya sama sekali.
    """
    divisi = await _departments(current_user["id"])
    return _lempar_bila_galat(
        await CertificateOfPaymentController.set_penyesuaian(
            cop_id,
            [a.model_dump() for a in data.adjustments],
            current_user["id"],
            _level(current_user),
            divisi,
        )
    )


@router.patch("/{cop_id}/approve")
async def setujui_cop(
    cop_id: int,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "approve"))],
):
    return _lempar_bila_galat(
        await CertificateOfPaymentController.approve(
            cop_id, current_user["id"], _level(current_user)
        )
    )


@router.delete("/{cop_id}")
async def hapus_cop(
    cop_id: int,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "delete"))],
):
    return _lempar_bila_galat(
        await CertificateOfPaymentController.delete(
            cop_id, current_user["id"], _level(current_user)
        )
    )


@router.get("/{cop_id}/tagihan")
async def tagihan_cop(
    cop_id: int,
    current_user: Annotated[User, Depends(require("certificate_of_payment", "read"))],
):
    """Sudah ditagihkan lewat pembelian mana? Kosong bila belum."""
    return _lempar_bila_galat(
        await CertificateOfPaymentController.tagihan(cop_id, _level(current_user))
    )
