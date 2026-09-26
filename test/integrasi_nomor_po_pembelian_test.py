"""
Mengganti nomor PO sebuah pembelian, lewat endpoint sungguhan.

Kenapa ini perlu dijaga ketat
-----------------------------

Nomor PO pada pembelian disimpan sebagai **TEKS**, bukan tautan. Tidak ada satu
pun penjaga basis data yang menolak nomor yang tidak pernah ada — yang terjadi
hanya pembelian yang diam-diam tidak menunjuk dokumen mana pun, dan baru
ketahuan ketika ada yang mencarinya, sering kali setahun kemudian saat
rekonsiliasi.

Layarnya memakai autocomplete, dan itu menutup jalur salah ketik. Tetapi
muatan permintaan dapat disusun sendiri oleh siapa pun yang membuka Network
tab, jadi pencocokannya harus di server.

Hal kedua yang dijaga: pembelian menyimpan **nama proyeknya sendiri**. Bila ia
tidak ikut berpindah saat nomor PO diganti, rekap per proyek menghitung
pembelian ini di proyek yang berbeda dari PO-nya — dan tidak ada yang tahu mana
yang benar. Proyeknya karena itu diambil dari dokumen PO-nya, bukan dari yang
dikirim layar.

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


async def _buat_po(bersihkan, proyek: str) -> str:
    """Satu purchase order aktif; yang dikembalikan nomornya."""
    from utils.database import database
    from models.purchase_order_model import purchase_orders_table as po

    nama = tanda()
    po_id = await database.execute(
        po.insert().values(
            name=nama,
            number=1,
            projectName=proyek,
            supplierID=1,
            date=d.today(),
            purchaseType="Jasa",
            templateVersion="1",
            dpp=1_000_000,
            ppn=11,
            otherValue=0,
            billing_requirements="[]",
            payment_term="CASH",
            revision=0,
            isApproved=True,
            isChecked=True,
            isDelete=False,
            createdAt=dt.now(),
            createdBy=1,
        )
    )
    bersihkan(po, po_id)
    return nama


async def _buat_pembelian(bersihkan, nomor_po: str, proyek: str) -> int:
    from utils.database import database
    from models.purchase_model import purchases_table

    t = tanda()
    purchase_id = await database.execute(
        purchases_table.insert().values(
            invoiceName=t,
            receiptName=t,
            supplierID=1,
            date=d.today(),
            purchaseOrderName=nomor_po,
            projectName=proyek,
            purchaseType="Jasa",
            procurementType="Jasa",
            dpp=1_000_000,
            ppn=11,
            pbbkb=0,
            pphPercentage=0,
            otherValue=0,
            isInvoiceAttached=False,
            isReceiptAttached=False,
            isTaxInvoiceAttached=False,
            isCopAttached=False,
            isCopyPurchaseOrderAttached=False,
            bankName="Bank Uji",
            bankAccountName="Rekening Uji",
            bankAccountNumber="000",
            paymentMethod="Transfer",
            isPaid=False,
            isDelete=False,
            createdAt=dt.now(),
            createdBy=1,
            lastStatus="ready",
            isInternal=False,
        )
    )
    bersihkan(purchases_table, purchase_id)
    return purchase_id


async def _baca(purchase_id: int):
    from utils.database import database
    from models.purchase_model import purchases_table

    return await database.fetch_one(
        purchases_table.select().where(purchases_table.c.id == purchase_id)
    )


def _muatan(**tambahan):
    """Muatan meta paling ringkas yang sah, plus yang diuji."""
    dasar = {
        "date": str(d.today()),
        "invoiceName": "INV-UJI",
        "receiptName": "KWT-UJI",
    }
    dasar.update(tambahan)
    return dasar


# ----------------------------------------------------------------------
# Jalur yang diminta
# ----------------------------------------------------------------------

async def test_nomor_po_dapat_diganti(klien, bersihkan):
    lama = await _buat_po(bersihkan, "PROYEK-A")
    baru = await _buat_po(bersihkan, "PROYEK-A")
    purchase_id = await _buat_pembelian(bersihkan, lama, "PROYEK-A")

    r = await klien.put(
        f"/purchases/{purchase_id}/meta",
        json=_muatan(purchaseOrderName=baru),
    )
    assert r.status_code == 200, r.text
    assert (await _baca(purchase_id))["purchaseOrderName"] == baru


async def test_proyek_ikut_pindah_mengikuti_po_barunya(klien, bersihkan):
    """
    Pembelian menyimpan nama proyeknya sendiri. Membiarkannya tertinggal
    membuat rekap per proyek menghitung pembelian ini di proyek yang berbeda
    dari PO-nya — dan tidak ada yang tahu mana yang benar.
    """
    lama = await _buat_po(bersihkan, "PROYEK-A")
    baru = await _buat_po(bersihkan, "PROYEK-B")
    purchase_id = await _buat_pembelian(bersihkan, lama, "PROYEK-A")

    r = await klien.put(
        f"/purchases/{purchase_id}/meta",
        json=_muatan(purchaseOrderName=baru),
    )
    assert r.status_code == 200, r.text

    baris = await _baca(purchase_id)
    assert baris["purchaseOrderName"] == baru
    assert baris["projectName"] == "PROYEK-B"


async def test_proyek_diambil_dari_po_bukan_dari_kiriman(klien, bersihkan):
    """
    Dua sumber untuk satu nilai berarti salah satunya pasti tertinggal.
    Proyek yang dikirim klien diabaikan; yang menentukan dokumen PO-nya.
    """
    lama = await _buat_po(bersihkan, "PROYEK-A")
    baru = await _buat_po(bersihkan, "PROYEK-B")
    purchase_id = await _buat_pembelian(bersihkan, lama, "PROYEK-A")

    r = await klien.put(
        f"/purchases/{purchase_id}/meta",
        json=_muatan(purchaseOrderName=baru, projectName="PROYEK-NGAWUR"),
    )
    assert r.status_code == 200, r.text
    assert (await _baca(purchase_id))["projectName"] == "PROYEK-B"


async def test_nomor_po_boleh_diganti_meski_sudah_ada_pembayaran(
    klien, bersihkan
):
    """
    Nomor PO keterangan, bukan nominal — tidak menggeser satu rupiah pun.
    Diperlakukan sama seperti nomor faktur pajak dan masa pajak, yang justru
    paling sering perlu dibetulkan SETELAH dokumennya dibayar.
    """
    from utils.database import database
    from models.payment_outgoing_model import payments_outgoing_table

    lama = await _buat_po(bersihkan, "PROYEK-A")
    baru = await _buat_po(bersihkan, "PROYEK-A")
    purchase_id = await _buat_pembelian(bersihkan, lama, "PROYEK-A")

    pembayaran_id = await database.execute(
        payments_outgoing_table.insert().values(
            date=d.today(),
            amount=1_110_000,
            purchaseID=purchase_id,
            createdAt=dt.now(),
            createdBy=1,
            isDelete=False,
            isApprove=True,
            status="ready",
        )
    )
    bersihkan(payments_outgoing_table, pembayaran_id)

    r = await klien.put(
        f"/purchases/{purchase_id}/meta",
        json=_muatan(purchaseOrderName=baru),
    )
    assert r.status_code == 200, r.text
    assert (await _baca(purchase_id))["purchaseOrderName"] == baru


# ----------------------------------------------------------------------
# Penjagaannya
# ----------------------------------------------------------------------

async def test_nomor_po_yang_tidak_ada_ditolak(klien, bersihkan):
    """
    Inti penjagaannya. Tanpa ini nomornya tersimpan apa adanya, tanpa galat,
    dan pembeliannya diam-diam tidak menunjuk dokumen mana pun.
    """
    lama = await _buat_po(bersihkan, "PROYEK-A")
    purchase_id = await _buat_pembelian(bersihkan, lama, "PROYEK-A")

    r = await klien.put(
        f"/purchases/{purchase_id}/meta",
        json=_muatan(purchaseOrderName="PO-YANG-TIDAK-PERNAH-ADA"),
    )
    assert r.status_code == 400, r.text
    assert (await _baca(purchase_id))["purchaseOrderName"] == lama


async def test_po_yang_sudah_dihapus_ditolak(klien, bersihkan):
    """
    Nomornya boleh saja masih ada di tabel, tetapi menautkan pembelian ke
    dokumen yang sudah dibatalkan justru kekeliruan yang sedang dicegah.
    """
    from utils.database import database
    from models.purchase_order_model import purchase_orders_table as po

    lama = await _buat_po(bersihkan, "PROYEK-A")
    mati = await _buat_po(bersihkan, "PROYEK-B")
    await database.execute(
        po.update().where(po.c.name == mati).values(isDelete=True)
    )
    purchase_id = await _buat_pembelian(bersihkan, lama, "PROYEK-A")

    r = await klien.put(
        f"/purchases/{purchase_id}/meta",
        json=_muatan(purchaseOrderName=mati),
    )
    assert r.status_code == 400, r.text
    assert (await _baca(purchase_id))["purchaseOrderName"] == lama


async def test_nomor_po_kosong_ditolak(klien, bersihkan):
    lama = await _buat_po(bersihkan, "PROYEK-A")
    purchase_id = await _buat_pembelian(bersihkan, lama, "PROYEK-A")

    r = await klien.put(
        f"/purchases/{purchase_id}/meta",
        json=_muatan(purchaseOrderName="   "),
    )
    assert r.status_code == 400, r.text
    assert (await _baca(purchase_id))["purchaseOrderName"] == lama


async def test_proyek_tidak_dapat_diubah_tanpa_mengganti_po(klien, bersihkan):
    """
    Proyek hanya bergerak BERSAMA nomor PO-nya.

    Membiarkannya diubah sendiri mengembalikan persis keadaan yang dicegah:
    pembelian yang proyeknya berbeda dari PO-nya, tanpa ada yang tahu mana
    yang benar.
    """
    lama = await _buat_po(bersihkan, "PROYEK-A")
    purchase_id = await _buat_pembelian(bersihkan, lama, "PROYEK-A")

    r = await klien.put(
        f"/purchases/{purchase_id}/meta",
        json=_muatan(projectName="PROYEK-NGAWUR"),
    )
    assert r.status_code == 200, r.text
    assert (await _baca(purchase_id))["projectName"] == "PROYEK-A"


async def test_mengirim_nomor_yang_sama_tidak_menyentuh_proyek(klien, bersihkan):
    """
    Nomor yang tidak berubah tidak boleh memicu apa pun — termasuk
    memindahkan proyek ke nilai PO-nya, yang pada dokumen lama dapat saja
    sudah berbeda karena alasan yang sah.
    """
    lama = await _buat_po(bersihkan, "PROYEK-A")
    purchase_id = await _buat_pembelian(bersihkan, lama, "PROYEK-LAIN")

    r = await klien.put(
        f"/purchases/{purchase_id}/meta",
        json=_muatan(purchaseOrderName=lama),
    )
    assert r.status_code == 200, r.text
    assert (await _baca(purchase_id))["projectName"] == "PROYEK-LAIN"


async def test_keterangan_lain_tetap_tersimpan(klien, bersihkan):
    """Penambahan nomor PO tidak boleh menjatuhkan bidang yang sudah ada."""
    lama = await _buat_po(bersihkan, "PROYEK-A")
    baru = await _buat_po(bersihkan, "PROYEK-A")
    purchase_id = await _buat_pembelian(bersihkan, lama, "PROYEK-A")

    r = await klien.put(
        f"/purchases/{purchase_id}/meta",
        json=_muatan(
            purchaseOrderName=baru,
            invoiceName="INV-BARU",
            taxInvoiceName="0100000000000001",
        ),
    )
    assert r.status_code == 200, r.text

    baris = await _baca(purchase_id)
    assert baris["invoiceName"] == "INV-BARU"
    assert baris["taxInvoiceName"] == "0100000000000001"
    assert baris["purchaseOrderName"] == baru
