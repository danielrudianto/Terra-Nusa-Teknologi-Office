from typing import Any, Dict, List, Optional

from repository.tender_repository import MINIMAL_PENAWARAN, TenderRepository
from utils.transaksi import atomik
from sqlalchemy import select

from models.master_item_model import master_item_table
from utils.database import database
from utils.logger_utils import log_error, log_info


async def periksa_baris_barang(jenis: Optional[str], baris: Optional[list]) -> Optional[Dict[str, Any]]:
    """
    Tender BARANG: setiap baris wajib menunjuk barang di katalog (`itemID`).

    Nama barang yang diketik bebas menghasilkan "Semen 50kg", "semen 50 kg",
    dan "Semen Tiga Roda" untuk barang yang sama — penawaran tidak dapat
    dibandingkan dan riwayat harga terpecah. Barang yang belum ada
    didaftarkan dulu di Master Barang.

    Tender JASA tidak disentuh: uraian pekerjaan memang bebas.
    Mengembalikan galat, atau None bila lolos.
    """
    if jenis != "barang" or baris is None:
        return None
    kosong = [i + 1 for i, b in enumerate(baris) if not b.get("itemID")]
    if kosong:
        return {
            "error": (
                "Baris barang harus dipilih dari katalog (baris "
                + ", ".join(map(str, kosong))
                + "). Daftarkan dulu di Master Barang bila belum ada."
            ),
            "status": 422,
        }
    ids = sorted({int(b["itemID"]) for b in baris})
    ada = await database.fetch_all(
        select(master_item_table.c.id).where(
            master_item_table.c.id.in_(ids),
            master_item_table.c.isDelete == 0,
        )
    )
    hilang = set(ids) - {int(r["id"]) for r in ada}
    if hilang:
        return {
            "error": "Sebagian barang tidak ditemukan di katalog (mungkin sudah dihapus).",
            "status": 422,
        }
    return None


class TenderController:
    #: Keadaan yang MASIH boleh disunting.
    #:
    #: Tender yang sudah selesai atau dibatalkan tidak lagi diubah: penawaran
    #: di bawahnya sudah dibandingkan dan keputusannya sudah diambil, sehingga
    #: mengubah permintaannya membuat alasan pemenang menunjuk sesuatu yang
    #: berbeda dari yang dinilai.
    STATUS_DAPAT_DISUNTING = ("draft", "berjalan")

    #: Keadaan yang boleh MENERIMA PENAWARAN.
    #:
    #: `draft` SENGAJA tidak termasuk, dan ini yang berubah.
    #:
    #: Sebelumnya penawaran memakai `STATUS_DAPAT_DISUNTING` yang sama persis
    #: dengan syarat menyunting tendernya — sehingga `draft` dan `berjalan`
    #: diperlakukan identik, dan tombol "sebarkan" praktis cuma mengganti
    #: label tanpa satu pun aturan yang berubah karenanya. Statusnya ada,
    #: tetapi tidak membedakan apa pun.
    #:
    #: Itu bukan sekadar tidak rapi. Draf adalah permintaan yang ISINYA MASIH
    #: BERUBAH: baris barang masih disusun, volumenya masih dibetulkan.
    #: Meminta pemasok memberi harga atas daftar yang belum selesai berarti
    #: harga yang masuk menjawab pertanyaan yang sudah tidak berlaku — dan
    #: tidak ada yang tahu penawaran mana yang menilai versi yang mana.
    STATUS_MENERIMA_PENAWARAN = ("berjalan",)

    @staticmethod
    @atomik
    async def buat(body: dict, user_id: int) -> Dict[str, Any]:
        baris = body.pop("items", [])
        galat = await periksa_baris_barang(body.get("tenderType"), baris)
        if galat:
            return galat
        hasil = await TenderRepository.buat(body, baris, user_id)
        if "error" not in hasil:
            log_info(f"Tender dibuat: {hasil.get('id')}")
        return hasil

    @staticmethod
    async def ambil(tender_id: int) -> Dict[str, Any]:
        hasil = await TenderRepository.ambil(tender_id)
        if hasil is None:
            return {"error": "Tender tidak ditemukan.", "status": 404}
        return hasil

    @staticmethod
    async def daftar(
        page: int,
        page_size: int,
        status: str,
        cari: str,
        sortBy: str = None,
        sortByDirection: str = "desc",
    ) -> Dict[str, Any]:
        return await TenderRepository.daftar(
            page, page_size, status, cari, sortBy, sortByDirection
        )

    @staticmethod
    @atomik
    async def ubah(tender_id: int, body: dict, user_id: int) -> Dict[str, Any]:
        """
        Ubah tender beserta baris permintaannya — SATU TRANSAKSI.

        Sebelumnya tidak: kepala tendernya tersimpan lebih dahulu, lalu
        penulisan barisnya dikerjakan terpisah. Ketika penulisan baris gagal,
        yang tertinggal adalah tender yang berubah sementara layar
        menampilkan "Terjadi kesalahan di server" — yang membacanya
        menyimpulkan simpanannya tidak jadi, lalu mengetik ulang di atas
        data yang sudah berubah.

        `@atomik` juga menggulung balik pada dict ber-`error`, bukan hanya
        pada pengecualian — lihat keterangannya di `utils/transaksi.py`.
        """
        tender = await TenderRepository.ambil(tender_id)
        if tender is None:
            return {"error": "Tender tidak ditemukan.", "status": 404}
        if "error" in tender:
            return tender

        if tender["status"] not in TenderController.STATUS_DAPAT_DISUNTING:
            return {
                "error": (
                    "Tender yang sudah selesai atau dibatalkan tidak dapat "
                    "diubah."
                ),
                "status": 409,
            }

        baris = body.pop("items", None)
        versi = body.pop("rowVersion", None)
        galat = await periksa_baris_barang(
            body.get("tenderType") or tender.get("tenderType"), baris
        )
        if galat:
            return galat
        return await TenderRepository.ubah(
            tender_id, body, baris, user_id, versi=versi
        )

    @staticmethod
    async def sebarkan(tender_id: int, user_id: int) -> Dict[str, Any]:
        """
        Tandai tender sudah disebarkan.

        Menandainya, bukan mengirimkannya: penyebarannya lewat WhatsApp dan
        dikerjakan orang. Yang dicatat di sini hanya bahwa permintaannya sudah
        keluar, supaya yang membukanya kelak tahu tender ini sedang menunggu
        balasan, bukan masih disusun.
        """
        tender = await TenderRepository.ambil(tender_id)
        if tender is None:
            return {"error": "Tender tidak ditemukan.", "status": 404}
        if "error" in tender:
            return tender

        if tender["status"] != "draft":
            return {
                "error": "Hanya tender berstatus draf yang dapat disebarkan.",
                "status": 409,
            }
        if not tender.get("items"):
            return {
                "error": "Tender tanpa baris permintaan tidak dapat disebarkan.",
                "status": 400,
            }

        return await TenderRepository.set_status(tender_id, "berjalan", user_id)

    @staticmethod
    async def batalkan(tender_id: int, user_id: int) -> Dict[str, Any]:
        tender = await TenderRepository.ambil(tender_id)
        if tender is None:
            return {"error": "Tender tidak ditemukan.", "status": 404}
        if "error" in tender:
            return tender
        if tender["status"] == "selesai":
            return {
                "error": (
                    "Tender yang pemenangnya sudah ditetapkan tidak dapat "
                    "dibatalkan."
                ),
                "status": 409,
            }
        return await TenderRepository.set_status(tender_id, "batal", user_id)

    @staticmethod
    async def hapus(tender_id: int, user_id: int) -> Dict[str, Any]:
        tender = await TenderRepository.ambil(tender_id)
        if tender is None:
            return {"error": "Tender tidak ditemukan.", "status": 404}
        if "error" in tender:
            return tender
        if tender["status"] == "selesai":
            return {
                "error": (
                    "Tender yang pemenangnya sudah ditetapkan tidak dapat "
                    "dihapus. Riwayat pengadaan harus tetap dapat ditinjau."
                ),
                "status": 409,
            }
        return await TenderRepository.hapus(tender_id, user_id)

    # ------------------------------------------------------------------
    # Penawaran
    # ------------------------------------------------------------------

    @staticmethod
    @atomik
    async def tambah_penawaran(
        tender_id: int, body: dict, user_id: int
    ) -> Dict[str, Any]:
        tender = await TenderRepository.ambil(tender_id)
        if tender is None:
            return {"error": "Tender tidak ditemukan.", "status": 404}
        if "error" in tender:
            return tender

        if tender["status"] not in TenderController.STATUS_MENERIMA_PENAWARAN:
            return {
                "error": (
                    "Tender ini masih draf. Setujui dan sebarkan dulu sebelum "
                    "penawaran dicatat — daftar permintaannya masih dapat "
                    "berubah, dan harga atas daftar yang belum selesai "
                    "menjawab pertanyaan yang sudah tidak berlaku."
                ),
                "status": 409,
            }

        supplier_id = body.get("supplierID")
        if await TenderRepository.pemasok_sudah_menawar(tender_id, supplier_id):
            return {
                "error": (
                    "Pemasok ini sudah punya penawaran pada tender ini. "
                    "Ubah penawarannya bila ada revisi."
                ),
                "status": 409,
            }

        # Baris yang tidak termasuk permintaan DITOLAK.
        #
        # `tenderItemID` datang dari layar dan dapat menunjuk ke mana saja.
        # Tanpa pemeriksaan ini, satu penawaran dapat menuliskan harga pada
        # baris tender LAIN — dan perbandingannya menampilkan angka yang
        # tidak pernah ditawarkan siapa pun.
        sah = {x["id"] for x in tender.get("items", [])}
        baris = [b for b in body.pop("items", []) if b.get("tenderItemID") in sah]

        # Keterangan berkategori disimpan di tabelnya sendiri, jadi
        # dikeluarkan dari muatan sebelum baris penawarannya ditulis —
        # `noteList` bukan kolom `tender_quotes`, dan meneruskannya ke INSERT
        # melempar "Unconsumed column names" yang lalu ditelan menjadi 500.
        keterangan = body.pop("noteList", None)

        return await TenderRepository.tambah_penawaran(
            tender_id, body, baris, user_id, keterangan
        )

    @staticmethod
    @atomik
    async def ubah_penawaran(
        tender_id: int, quote_id: int, body: dict, user_id: int
    ) -> Dict[str, Any]:
        tender = await TenderRepository.ambil(tender_id)
        if tender is None:
            return {"error": "Tender tidak ditemukan.", "status": 404}
        if "error" in tender:
            return tender
        if tender["status"] not in TenderController.STATUS_MENERIMA_PENAWARAN:
            return {
                "error": (
                    "Tender ini masih draf. Setujui dan sebarkan dulu sebelum "
                    "penawaran diubah."
                ),
                "status": 409,
            }

        penawaran = await TenderRepository.penawaran_satu(quote_id)
        if penawaran is None or penawaran["tenderID"] != tender_id:
            return {"error": "Penawaran tidak ditemukan.", "status": 404}

        sah = {x["id"] for x in tender.get("items", [])}
        baris = body.pop("items", None)
        if baris is not None:
            baris = [b for b in baris if b.get("tenderItemID") in sah]

        # Lihat keterangan pada `tambah_penawaran`.
        keterangan = body.pop("noteList", None)

        return await TenderRepository.ubah_penawaran(
            quote_id, body, baris, user_id, keterangan
        )

    @staticmethod
    async def tutup_tanpa_pemenang(
        tender_id: int, alasan: str, user_id: int
    ) -> Dict[str, Any]:
        """
        Tutup tender tanpa memilih pemasok.

        Penawarannya terlalu mahal seluruhnya, pekerjaannya jadi dikerjakan
        sendiri, atau kebutuhannya berubah setelah penawaran masuk. Prosesnya
        berjalan sampai habis — berbeda dari `batalkan`, yang menghentikannya
        di tengah.

        `MINIMAL_PENAWARAN` SENGAJA TIDAK berlaku di sini. Tender yang ditutup
        tanpa pemenang justru kerap tender yang penawarannya tidak pernah
        cukup, dan menuntut tiga akan memaksanya menggantung selamanya —
        tampil sebagai pekerjaan yang belum selesai padahal keputusannya sudah
        diambil berbulan-bulan lalu.

        Yang tetap dituntut: alasan tertulis. Keputusan TIDAK MEMBELI-lah yang
        paling sering dipertanyakan setahun kemudian, dan yang paling sedikit
        meninggalkan dokumen.
        """
        tender = await TenderRepository.ambil(tender_id)
        if tender is None:
            return {"error": "Tender tidak ditemukan.", "status": 404}
        if "error" in tender:
            return tender

        if tender["status"] == "selesai":
            return {
                "error": "Tender ini sudah ditutup.",
                "status": 409,
            }
        if tender["status"] == "batal":
            return {
                "error": "Tender yang sudah dibatalkan tidak perlu ditutup.",
                "status": 409,
            }

        hasil = await TenderRepository.tutup_tanpa_pemenang(
            tender_id, alasan, user_id
        )
        if "error" not in hasil:
            log_info(f"Tender {tender_id} ditutup tanpa pemenang")
        return hasil

    @staticmethod
    async def hapus_penawaran(
        tender_id: int, quote_id: int, user_id: int
    ) -> Dict[str, Any]:
        tender = await TenderRepository.ambil(tender_id)
        if tender is None or "error" in tender:
            return {"error": "Tender tidak ditemukan.", "status": 404}

        if tender.get("winnerQuoteID") == quote_id:
            return {
                "error": (
                    "Penawaran yang ditetapkan sebagai pemenang tidak dapat "
                    "dihapus."
                ),
                "status": 409,
            }

        penawaran = await TenderRepository.penawaran_satu(quote_id)
        if penawaran is None or penawaran["tenderID"] != tender_id:
            return {"error": "Penawaran tidak ditemukan.", "status": 404}

        return await TenderRepository.hapus_penawaran(quote_id, user_id)

    @staticmethod
    async def tetapkan_pemenang(
        tender_id: int, quote_id: int, alasan: str, user_id: int
    ) -> Dict[str, Any]:
        """
        Tetapkan pemenang tender.

        Menuntut PALING SEDIKIT tiga penawaran. Keputusan pengadaan yang hanya
        membandingkan dua penawaran mudah tampak wajar padahal tidak pernah
        diuji pasar — dan yang meninjaunya kelak tidak punya cara mengetahui
        bahwa pembandingnya memang tidak ada.
        """
        tender = await TenderRepository.ambil(tender_id)
        if tender is None:
            return {"error": "Tender tidak ditemukan.", "status": 404}
        if "error" in tender:
            return tender

        if tender["status"] == "selesai":
            return {
                "error": "Pemenang tender ini sudah ditetapkan.",
                "status": 409,
            }
        if tender["status"] == "batal":
            return {
                "error": "Tender yang sudah dibatalkan tidak punya pemenang.",
                "status": 409,
            }

        jumlah = await TenderRepository.jumlah_penawaran(tender_id)
        if jumlah < MINIMAL_PENAWARAN:
            return {
                "error": (
                    f"Perlu paling sedikit {MINIMAL_PENAWARAN} penawaran "
                    f"sebelum pemenang dapat ditetapkan; baru ada {jumlah}."
                ),
                "status": 409,
            }

        penawaran = await TenderRepository.penawaran_satu(quote_id)
        if penawaran is None or penawaran["tenderID"] != tender_id:
            return {
                "error": "Penawaran tidak ditemukan pada tender ini.",
                "status": 404,
            }

        hasil = await TenderRepository.tetapkan_pemenang(
            tender_id, quote_id, alasan, user_id
        )
        if "error" not in hasil:
            log_info(f"Pemenang tender {tender_id}: penawaran {quote_id}")
        return hasil
