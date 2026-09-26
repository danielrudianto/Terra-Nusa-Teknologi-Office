"""
Status lunas pembelian, lewat basis data sungguhan.

Rumusnya sudah dijaga di `nilai_pembelian_test.py`. Yang dijaga DI SINI adalah
akibatnya pada baris yang tersimpan — sebab kegagalan yang dilaporkan bukan
"angkanya salah", melainkan "sudah saya selaraskan, tetap disebut belum
dibayar".

Urutan yang mematikan itu perlu benar-benar dijalankan untuk terlihat:

    1. pembayaran disetujui  -> `isPaid` menjadi True   (rumus lengkap)
    2. status diselaraskan   -> `isPaid` kembali False  (rumus tanpa PPh)

Langkah kedua menghapus hasil langkah pertama, tanpa galat. Menguji rumusnya
saja tidak menangkap ini; yang menangkapnya hanya membaca `isPaid` KEMBALI
dari basis data sesudah penyelarasan berjalan.

Lihat `test/_integrasi.py` untuk cara menjalankannya.
"""

from datetime import date as d, datetime as dt

import pytest

from _integrasi import (  # noqa: F401
    butuh_db,
    sambungan,
    klien,
    bersihkan,
    tanda,
)

pytestmark = butuh_db


async def _buat_pembelian(
    bersihkan,
    dpp: float,
    ppn: float,
    pph: float,
    other: float = 0,
    lunas: bool = False,
) -> int:
    """
    Pembelian ditulis langsung ke tabelnya.

    Lewat endpoint, satu pembelian menyeret pemasok, purchase order,
    penomoran, dan lampiran ikut serta — dan kegagalan di salah satunya akan
    tampak seperti kegagalan uji ini. Yang diuji di sini hanya perhitungan
    status lunasnya, jadi barisnya dibuat sesederhana yang dilihat kueri itu.
    """
    from utils.database import database
    from models.purchase_model import purchases_table

    t = tanda()
    purchase_id = await database.execute(
        purchases_table.insert().values(
            invoiceName=t,
            receiptName=t,
            supplierID=1,
            date=d.today(),
            purchaseOrderName=t,
            projectName="UJI",
            purchaseType="Jasa",
            procurementType="Jasa",
            dpp=dpp,
            ppn=ppn,
            pbbkb=0,
            pphPercentage=pph,
            otherValue=other,
            isInvoiceAttached=False,
            isReceiptAttached=False,
            isTaxInvoiceAttached=False,
            isCopAttached=False,
            isCopyPurchaseOrderAttached=False,
            bankName="Bank Uji",
            bankAccountName="Rekening Uji",
            bankAccountNumber="000",
            paymentMethod="Transfer",
            isPaid=lunas,
            isDelete=False,
            createdAt=dt.now(),
            createdBy=1,
            lastStatus="ready",
            isInternal=False,
        )
    )
    bersihkan(purchases_table, purchase_id)
    return purchase_id


async def _buat_pembayaran(bersihkan, purchase_id: int, nilai: float) -> int:
    from utils.database import database
    from models.payment_outgoing_model import payments_outgoing_table

    pembayaran_id = await database.execute(
        payments_outgoing_table.insert().values(
            date=d.today(),
            amount=nilai,
            purchaseID=purchase_id,
            createdAt=dt.now(),
            createdBy=1,
            isDelete=False,
            isApprove=True,
            status="ready",
        )
    )
    bersihkan(payments_outgoing_table, pembayaran_id)
    return pembayaran_id


async def _apakah_lunas(purchase_id: int) -> bool:
    from utils.database import database
    from models.purchase_model import purchases_table

    baris = await database.fetch_one(
        purchases_table.select().where(purchases_table.c.id == purchase_id)
    )
    return bool(baris["isPaid"])


async def _selaraskan(purchase_id: int) -> None:
    from controllers.payment_outgoing_controller import PaymentOutgoingController

    await PaymentOutgoingController.selaraskan_dokumen("purchase", purchase_id, 1)


# ----------------------------------------------------------------------
# Kejadian yang dilaporkan
# ----------------------------------------------------------------------

async def test_pembelian_berpph_yang_dibayar_penuh_menjadi_lunas(klien, bersihkan):
    """
    Kejadian pertama: DPP 280.080.000, PPN 11%, PPh 2,65%.

    Yang ditransfer 44.145.000 ... bukan — 303.466.680, tepat sebesar
    tagihan setelah PPh dipotong. Sebelum perbaikan, penyelarasan menuntut
    310.888.800 dan menyimpulkan masih kurang 7.422.120 — jumlah yang tidak
    akan pernah ditransfer siapa pun, karena disetorkan ke kas negara.
    """
    purchase_id = await _buat_pembelian(bersihkan, 280_080_000, 11, 2.65)
    await _buat_pembayaran(bersihkan, purchase_id, 303_466_680)

    await _selaraskan(purchase_id)

    assert await _apakah_lunas(purchase_id), (
        "pembelian yang sudah dibayar penuh tetap bertanda belum dibayar"
    )


async def test_kejadian_kedua_juga_menjadi_lunas(klien, bersihkan):
    """DPP 40.500.000, PPN 11%, PPh 2% -> dibayar 44.145.000."""
    purchase_id = await _buat_pembelian(bersihkan, 40_500_000, 11, 2)
    await _buat_pembayaran(bersihkan, purchase_id, 44_145_000)

    await _selaraskan(purchase_id)

    assert await _apakah_lunas(purchase_id)


async def test_penyelarasan_tidak_mencabut_lunas_yang_benar(klien, bersihkan):
    """
    Inti keluhannya: penyelarasan MENCABUT status lunas yang sudah benar.

    Dokumennya dimulai dalam keadaan lunas — persis seperti sesudah
    pembayarannya disetujui — lalu diselaraskan. Sesudahnya ia harus tetap
    lunas. Dijalankan dua kali, karena tombolnya memang dapat ditekan
    berulang.
    """
    purchase_id = await _buat_pembelian(
        bersihkan, 280_080_000, 11, 2.65, lunas=True
    )
    await _buat_pembayaran(bersihkan, purchase_id, 303_466_680)

    await _selaraskan(purchase_id)
    assert await _apakah_lunas(purchase_id)

    await _selaraskan(purchase_id)
    assert await _apakah_lunas(purchase_id), (
        "penyelarasan kedua mencabut status lunas"
    )


# ----------------------------------------------------------------------
# Arah sebaliknya — penjaganya tidak boleh kebablasan
# ----------------------------------------------------------------------

async def test_kurang_bayar_tetap_belum_lunas(klien, bersihkan):
    """
    Rumus yang memotong PPh tidak boleh membuat kekurangan bayar sungguhan
    ikut lolos. Yang dibayar di sini kurang 1 juta dari yang seharusnya.
    """
    purchase_id = await _buat_pembelian(bersihkan, 40_500_000, 11, 2)
    await _buat_pembayaran(bersihkan, purchase_id, 43_145_000)

    await _selaraskan(purchase_id)

    assert not await _apakah_lunas(purchase_id)


async def test_status_lunas_dicabut_saat_pembayarannya_dihapus(klien, bersihkan):
    """
    Dua arah, bukan satu.

    Penyelarasan harus juga MENCABUT status lunas ketika pembayarannya sudah
    tidak berlaku — kalau tidak, dokumen bertanda lunas padahal uangnya tidak
    pernah keluar, dan itu kekeliruan yang jauh lebih mahal.
    """
    from utils.database import database
    from models.payment_outgoing_model import payments_outgoing_table

    purchase_id = await _buat_pembelian(
        bersihkan, 40_500_000, 11, 2, lunas=True
    )
    pembayaran_id = await _buat_pembayaran(bersihkan, purchase_id, 44_145_000)

    await database.execute(
        payments_outgoing_table.update()
        .where(payments_outgoing_table.c.id == pembayaran_id)
        .values(isDelete=True)
    )

    await _selaraskan(purchase_id)

    assert not await _apakah_lunas(purchase_id), (
        "status lunas bertahan padahal pembayarannya sudah dihapus"
    )


async def test_other_value_ikut_diperhitungkan(klien, bersihkan):
    """
    `otherValue` MENAMBAH tagihan, jadi mengabaikannya menandai lunas
    dokumen yang sebenarnya masih kurang bayar — arah kekeliruan yang
    berlawanan dengan PPh, dan yang lebih berbahaya.
    """
    purchase_id = await _buat_pembelian(
        bersihkan, 40_500_000, 11, 2, other=1_000_000
    )
    await _buat_pembayaran(bersihkan, purchase_id, 44_145_000)

    await _selaraskan(purchase_id)

    assert not await _apakah_lunas(purchase_id), (
        "otherValue tidak ikut dihitung; dokumen kurang bayar ditandai lunas"
    )

    await _buat_pembayaran(bersihkan, purchase_id, 1_000_000)
    await _selaraskan(purchase_id)
    assert await _apakah_lunas(purchase_id)
