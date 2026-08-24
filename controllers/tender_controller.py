from typing import Any, Dict, List, Optional

from repository.tender_repository import MINIMAL_PENAWARAN, TenderRepository
from utils.logger_utils import log_error, log_info


class TenderController:
    #: Keadaan yang MASIH boleh disunting.
    #:
    #: Tender yang sudah selesai atau dibatalkan tidak lagi diubah: penawaran
    #: di bawahnya sudah dibandingkan dan keputusannya sudah diambil, sehingga
    #: mengubah permintaannya membuat alasan pemenang menunjuk sesuatu yang
    #: berbeda dari yang dinilai.
    STATUS_DAPAT_DISUNTING = ("draft", "berjalan")

    @staticmethod
    async def buat(body: dict, user_id: int) -> Dict[str, Any]:
        baris = body.pop("items", [])
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
    async def ubah(tender_id: int, body: dict, user_id: int) -> Dict[str, Any]:
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
        return await TenderRepository.ubah(tender_id, body, baris, user_id)

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
    async def tambah_penawaran(
        tender_id: int, body: dict, user_id: int
    ) -> Dict[str, Any]:
        tender = await TenderRepository.ambil(tender_id)
        if tender is None:
            return {"error": "Tender tidak ditemukan.", "status": 404}
        if "error" in tender:
            return tender

        if tender["status"] not in TenderController.STATUS_DAPAT_DISUNTING:
            return {
                "error": (
                    "Penawaran hanya dapat dicatat selama tendernya masih "
                    "berjalan."
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

        return await TenderRepository.tambah_penawaran(
            tender_id, body, baris, user_id
        )

    @staticmethod
    async def ubah_penawaran(
        tender_id: int, quote_id: int, body: dict, user_id: int
    ) -> Dict[str, Any]:
        tender = await TenderRepository.ambil(tender_id)
        if tender is None:
            return {"error": "Tender tidak ditemukan.", "status": 404}
        if "error" in tender:
            return tender
        if tender["status"] not in TenderController.STATUS_DAPAT_DISUNTING:
            return {
                "error": (
                    "Penawaran hanya dapat diubah selama tendernya masih "
                    "berjalan."
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

        return await TenderRepository.ubah_penawaran(
            quote_id, body, baris, user_id
        )

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
