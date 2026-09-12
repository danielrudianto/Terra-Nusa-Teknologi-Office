from datetime import datetime as dt
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, insert, select, update

from models.master_item_model import master_item_table
from models.supplier_model import suppliers_table
from models.tender_model import (
    tender_items_table,
    tender_quote_items_table,
    tender_quote_notes_table,
    tender_quotes_table,
    tenders_table,
)
from utils.database import database
from utils.logger_utils import log_error

#: Penawaran paling sedikit sebelum pemenang dapat ditetapkan.
#:
#: Keputusan pengadaan yang hanya membandingkan dua penawaran mudah tampak
#: wajar padahal tidak pernah diuji pasar. Angkanya keputusan pemilik, bukan
#: aturan luar — dikumpulkan di sini supaya dapat diubah di satu tempat.
MINIMAL_PENAWARAN = 3


class TenderRepository:
    @staticmethod
    async def nomor_berikutnya() -> int:
        """
        Nomor urut berikutnya.

        `MAX(number) + 1`, bukan `COUNT`: tender yang dihapus tetap terhitung
        supaya nomornya tidak pernah dipakai ulang — dua tender bernomor sama
        membuat rujukan pada percakapan WhatsApp menjadi taksa.
        """
        try:
            tertinggi = await database.fetch_val(
                select(func.max(tenders_table.c.number))
            )
            return (tertinggi or 0) + 1
        except Exception as e:
            log_error(f"Error reading next tender number: {str(e)}")
            return 1

    @staticmethod
    async def buat(nilai: dict, baris: List[dict], user_id: int) -> Dict[str, Any]:
        try:
            nomor = await TenderRepository.nomor_berikutnya()
            tender_id = await database.execute(
                insert(tenders_table).values(
                    **nilai,
                    number=nomor,
                    status="draft",
                    createdAt=dt.now(),
                    createdBy=user_id,
                )
            )
            await TenderRepository._tulis_baris(tender_id, baris)
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="tenders",
                entityID=int(tender_id),
                action="create",
                userID=user_id,
            )
            return {"id": tender_id, "number": nomor}
        except Exception as e:
            log_error(f"Error creating tender: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def _tulis_baris(tender_id: int, baris: List[dict]) -> None:
        """
        Tulis ulang seluruh baris permintaan.

        Baris LAMA dihapus keras, bukan ditandai — berbeda dari tendernya
        sendiri. Baris permintaan tidak dirujuk dokumen mana pun selain
        penawaran atasnya, dan penawaran hanya ada setelah tendernya
        disebarkan; selama masih draf, tidak ada yang kehilangan rujukan.
        """
        await database.execute(
            tender_items_table.delete().where(
                tender_items_table.c.tenderID == tender_id
            )
        )
        for urut, b in enumerate(baris):
            await database.execute(
                insert(tender_items_table).values(
                    tenderID=tender_id,
                    itemID=b.get("itemID"),
                    name=b.get("name"),
                    specification=b.get("specification"),
                    quantity=b.get("quantity"),
                    unit=b.get("unit"),
                    sortOrder=b.get("sortOrder", urut),
                )
            )

    @staticmethod
    async def ambil(tender_id: int) -> Optional[Dict[str, Any]]:
        """Tender beserta baris permintaan dan seluruh penawarannya."""
        try:
            baris = await database.fetch_one(
                select(tenders_table).where(
                    tenders_table.c.id == tender_id,
                    tenders_table.c.isDelete == False,  # noqa: E712
                )
            )
            if baris is None:
                return None

            hasil = dict(baris)
            hasil["items"] = [
                dict(x)
                for x in await database.fetch_all(
                    select(tender_items_table)
                    .where(tender_items_table.c.tenderID == tender_id)
                    .order_by(tender_items_table.c.sortOrder.asc())
                )
            ]
            hasil["quotes"] = await TenderRepository.penawaran(tender_id)
            return hasil
        except Exception as e:
            log_error(f"Error fetching tender: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def penawaran(tender_id: int) -> List[Dict[str, Any]]:
        """
        Seluruh penawaran pada satu tender, beserta harga per barisnya.

        Nama pemasok ikut diambil, bukan hanya `supplierID`: layar
        perbandingan menampilkannya berdampingan, dan mengambilnya terpisah
        berarti satu permintaan tambahan per penawaran.
        """
        rows = await database.fetch_all(
            select(
                tender_quotes_table,
                suppliers_table.c.name.label("supplierName"),
                suppliers_table.c.prefix.label("supplierPrefix"),
            )
            .select_from(
                tender_quotes_table.join(
                    suppliers_table,
                    tender_quotes_table.c.supplierID == suppliers_table.c.id,
                )
            )
            .where(
                tender_quotes_table.c.tenderID == tender_id,
                tender_quotes_table.c.isDelete == False,  # noqa: E712
            )
            .order_by(tender_quotes_table.c.id.asc())
        )

        hasil = []
        for r in rows:
            q = dict(r)
            q["items"] = [
                dict(x)
                for x in await database.fetch_all(
                    select(tender_quote_items_table).where(
                        tender_quote_items_table.c.quoteID == q["id"]
                    )
                )
            ]
            q["noteList"] = await TenderRepository._keterangan(q)
            hasil.append(q)
        return hasil

    @staticmethod
    async def _keterangan(quote: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Keterangan berkategori satu penawaran.

        Dengan JALAN MUNDUR untuk penawaran lama: sebelum kategori ada,
        seluruh keterangan tersimpan sebagai satu teks bebas di
        `tender_quotes.notes`. Penawaran yang belum pernah disunting sejak itu
        tidak punya satu pun baris di `tender_quote_notes` — dan tanpa jalan
        mundur ini, keterangannya menghilang dari layar seolah tidak pernah
        ditulis.

        Teks lamanya ditampilkan sebagai satu keterangan berkategori
        `lainnya`, ditandai `warisan` supaya layar dapat menyebutkan bahwa ia
        belum dipilah. Begitu penawarannya disunting, `_tulis_keterangan`
        mengosongkan kolom lamanya, dan jalan mundur ini berhenti dengan
        sendirinya.
        """
        baris = [
            dict(x)
            for x in await database.fetch_all(
                select(tender_quote_notes_table)
                .where(tender_quote_notes_table.c.quoteID == quote["id"])
                .order_by(
                    tender_quote_notes_table.c.sortOrder.asc(),
                    tender_quote_notes_table.c.id.asc(),
                )
            )
        ]
        if baris:
            return baris

        lama = str(quote.get("notes") or "").strip()
        if not lama:
            return []
        return [
            {
                "id": None,
                "quoteID": quote["id"],
                "category": "lainnya",
                "content": lama,
                "sortOrder": 0,
                # Belum dipilah ke kategori; berasal dari kolom teks bebas.
                "warisan": True,
            }
        ]

    #: Kolom yang boleh dipakai mengurutkan, dipetakan dari nama di layar.
    #:
    #: Daftar TERTUTUP, bukan nama kolom yang diteruskan apa adanya: nama
    #: yang datang dari luar dan langsung dipakai menyusun `ORDER BY`
    #: membuka jalan bagi kolom yang tidak dimaksudkan untuk dibaca — dan
    #: pada sebagian basis data, bagi hal yang lebih buruk daripada itu.
    #:
    #: `quoteCount` sengaja TIDAK ada di sini. Ia bukan kolom melainkan
    #: hasil hitungan yang dijalankan sesudah barisnya diambil, sehingga
    #: mengurutkan dengannya hanya akan mengurutkan halaman yang sedang
    #: tampil — bukan seluruh datanya. Yang terlihat mengurut, padahal
    #: tidak.
    SORTABLE = {
        "number": tenders_table.c.number,
        "name": tenders_table.c.name,
        "date": tenders_table.c.date,
        "dueDate": tenders_table.c.dueDate,
        "projectName": tenders_table.c.projectName,
        "tenderType": tenders_table.c.tenderType,
        "status": tenders_table.c.status,
        "createdAt": tenders_table.c.createdAt,
    }

    @staticmethod
    def _urutan(sortBy: str = None, sortByDirection: str = "desc"):
        """Kolom pengurut; jatuh ke id bila kolomnya tidak dikenal.

        Cadangannya `id`, bukan salah satu kolom isian: itulah urutan yang
        berlaku sebelum pengurutan ini ada, sehingga permintaan tanpa
        pengurutan menghasilkan daftar yang sama seperti sebelumnya.
        """
        kolom = TenderRepository.SORTABLE.get(sortBy, tenders_table.c.id)
        return (
            kolom.asc()
            if str(sortByDirection).lower() == "asc"
            else kolom.desc()
        )

    @staticmethod
    async def daftar(
        page: int = 1,
        page_size: int = 10,
        status: str = "",
        cari: str = "",
        sortBy: str = None,
        sortByDirection: str = "desc",
    ) -> Dict[str, Any]:
        try:
            syarat = [tenders_table.c.isDelete == False]  # noqa: E712
            if status:
                syarat.append(tenders_table.c.status == status)
            if cari:
                syarat.append(tenders_table.c.name.ilike(f"%{cari}%"))

            total = await database.fetch_val(
                select(func.count()).select_from(tenders_table).where(and_(*syarat))
            )
            rows = await database.fetch_all(
                select(tenders_table)
                .where(and_(*syarat))
                .order_by(TenderRepository._urutan(sortBy, sortByDirection))
                .limit(page_size)
                .offset((page - 1) * page_size)
            )

            data = []
            for r in rows:
                d = dict(r)
                # Banyaknya penawaran ikut dihitung.
                #
                # Layar daftar menandai tender yang belum cukup penawarannya;
                # tanpa angka ini, yang membukanya harus masuk satu per satu
                # untuk mengetahui mana yang masih menunggu.
                d["quoteCount"] = await database.fetch_val(
                    select(func.count())
                    .select_from(tender_quotes_table)
                    .where(
                        tender_quotes_table.c.tenderID == d["id"],
                        tender_quotes_table.c.isDelete == False,  # noqa: E712
                    )
                )
                data.append(d)

            return {"data": data, "count": total or 0}
        except Exception as e:
            log_error(f"Error listing tenders: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def ubah(
        tender_id: int,
        nilai: dict,
        baris: Optional[List[dict]],
        user_id: int,
    ) -> Dict[str, Any]:
        try:
            if nilai:
                await database.execute(
                    update(tenders_table)
                    .where(tenders_table.c.id == tender_id)
                    .values(**nilai, updatedAt=dt.now(), updatedBy=user_id)
                )
            if baris is not None:
                await TenderRepository._tulis_baris(tender_id, baris)
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="tenders",
                entityID=int(tender_id),
                action="update",
                userID=user_id,
            )
            return {"id": tender_id}
        except Exception as e:
            log_error(f"Error updating tender: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def set_status(tender_id: int, status: str, user_id: int) -> Dict[str, Any]:
        try:
            await database.execute(
                update(tenders_table)
                .where(tenders_table.c.id == tender_id)
                .values(status=status, updatedAt=dt.now(), updatedBy=user_id)
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="tenders",
                entityID=int(tender_id),
                action="update_status",
                userID=user_id,
            )
            return {"id": tender_id, "status": status}
        except Exception as e:
            log_error(f"Error updating tender status: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def tetapkan_pemenang(
        tender_id: int, quote_id: int, alasan: str, user_id: int
    ) -> Dict[str, Any]:
        try:
            await database.execute(
                update(tenders_table)
                .where(tenders_table.c.id == tender_id)
                .values(
                    winnerQuoteID=quote_id,
                    winnerReason=alasan,
                    decidedAt=dt.now(),
                    decidedBy=user_id,
                    status="selesai",
                    updatedAt=dt.now(),
                    updatedBy=user_id,
                )
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="tenders",
                entityID=int(tender_id),
                action="set_winner",
                userID=user_id,
            )
            return {"id": tender_id, "winnerQuoteID": quote_id}
        except Exception as e:
            log_error(f"Error setting tender winner: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def tutup_tanpa_pemenang(
        tender_id: int, alasan: str, user_id: int
    ) -> Dict[str, Any]:
        """
        Tutup tender tanpa memilih siapa pun.

        Tersimpan sebagai `status = 'selesai'` dengan `winnerQuoteID` tetap
        NULL — bukan status baru. Keadaannya sudah dapat diungkapkan oleh
        kolom yang ada, dan menambah nilai status baru berarti setiap
        penyaring, chip, dan laporan yang mengenal empat nilai harus ikut
        diubah; yang terlewat akan diam-diam menyembunyikan tendernya.

        Berbeda dari `batalkan`: yang dibatalkan dihentikan sebelum selesai,
        yang ditutup ini prosesnya berjalan sampai habis dan tidak ada yang
        dipilih.
        """
        try:
            await database.execute(
                update(tenders_table)
                .where(tenders_table.c.id == tender_id)
                .values(
                    winnerQuoteID=None,
                    winnerReason=alasan,
                    decidedAt=dt.now(),
                    decidedBy=user_id,
                    status="selesai",
                    updatedAt=dt.now(),
                    updatedBy=user_id,
                )
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="tenders",
                entityID=int(tender_id),
                action="close_no_winner",
                userID=user_id,
                note=alasan,
            )
            return {"id": tender_id, "winnerQuoteID": None}
        except Exception as e:
            log_error(f"Error closing tender without winner: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def hapus(tender_id: int, user_id: int) -> Dict[str, Any]:
        """
        Hapus lunak.

        Barisnya tetap ada: tender yang sudah disebar dirujuk percakapan
        WhatsApp dengan pemasok, dan menghapusnya membuat nomor yang sudah
        beredar menunjuk ke sesuatu yang tidak ada.
        """
        try:
            await database.execute(
                update(tenders_table)
                .where(tenders_table.c.id == tender_id)
                .values(isDelete=True, deletedAt=dt.now(), deletedBy=user_id)
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="tenders",
                entityID=int(tender_id),
                action="delete",
                userID=user_id,
            )
            return {"id": tender_id}
        except Exception as e:
            log_error(f"Error deleting tender: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    # ------------------------------------------------------------------
    # Penawaran
    # ------------------------------------------------------------------

    @staticmethod
    async def tambah_penawaran(
        tender_id: int,
        nilai: dict,
        baris: List[dict],
        user_id: int,
        keterangan: Optional[List[dict]] = None,
    ) -> Dict[str, Any]:
        try:
            quote_id = await database.execute(
                insert(tender_quotes_table).values(
                    tenderID=tender_id,
                    **nilai,
                    createdAt=dt.now(),
                    createdBy=user_id,
                )
            )
            await TenderRepository._tulis_baris_penawaran(quote_id, baris)
            if keterangan is not None:
                await TenderRepository._tulis_keterangan(quote_id, keterangan)
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="tender_quotes",
                entityID=int(quote_id),
                action="create",
                userID=user_id,
            )
            return {"id": quote_id}
        except Exception as e:
            log_error(f"Error adding tender quote: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def _tulis_keterangan(quote_id: int, keterangan: List[dict]) -> None:
        """
        Ganti seluruh keterangan berkategori satu penawaran.

        Dihapus dulu lalu ditulis ulang, sama seperti baris harganya: tanpa itu
        keterangan yang DIHAPUS di layar tetap tertinggal di basis data, dan
        pada tabel perbandingan ia muncul kembali di sebelah keterangan
        penggantinya.

        Kolom lama `tender_quotes.notes` DIKOSONGKAN di sini. Selama masih
        terisi, `penawaran()` menampilkannya sebagai keterangan berkategori
        `lainnya` demi penawaran lama — dan bila keduanya terisi sekaligus,
        satu penawaran menampilkan keterangannya dua kali.
        """
        await database.execute(
            tender_quote_notes_table.delete().where(
                tender_quote_notes_table.c.quoteID == quote_id
            )
        )
        for urut, k in enumerate(keterangan or []):
            isi = str(k.get("content") or "").strip()
            # Keterangan kosong tidak disimpan. Barisnya ada di layar hanya
            # karena isiannya baru ditambahkan lalu ditinggalkan.
            if not isi:
                continue
            await database.execute(
                insert(tender_quote_notes_table).values(
                    quoteID=quote_id,
                    category=k.get("category") or "lainnya",
                    content=isi,
                    sortOrder=k.get("sortOrder", urut),
                )
            )

        await database.execute(
            update(tender_quotes_table)
            .where(tender_quotes_table.c.id == quote_id)
            .values(notes=None)
        )

    @staticmethod
    async def _tulis_baris_penawaran(quote_id: int, baris: List[dict]) -> None:
        await database.execute(
            tender_quote_items_table.delete().where(
                tender_quote_items_table.c.quoteID == quote_id
            )
        )
        for b in baris:
            # Baris tanpa harga TIDAK disimpan.
            #
            # Tidak setiap pemasok menawar seluruh permintaan. Menyimpan
            # barisnya dengan harga kosong membuat perbandingan harus
            # membedakan "tidak menawar" dari "menawar nol" pada setiap
            # perhitungan; meniadakan barisnya membuat perbedaan itu jelas
            # dengan sendirinya.
            if b.get("price") is None:
                continue
            await database.execute(
                insert(tender_quote_items_table).values(
                    quoteID=quote_id,
                    tenderItemID=b.get("tenderItemID"),
                    price=b.get("price"),
                    notes=b.get("notes"),
                )
            )

    @staticmethod
    async def ubah_penawaran(
        quote_id: int,
        nilai: dict,
        baris: Optional[List[dict]],
        user_id: int,
        keterangan: Optional[List[dict]] = None,
    ) -> Dict[str, Any]:
        try:
            if nilai:
                await database.execute(
                    update(tender_quotes_table)
                    .where(tender_quotes_table.c.id == quote_id)
                    .values(**nilai, updatedAt=dt.now(), updatedBy=user_id)
                )
            if baris is not None:
                await TenderRepository._tulis_baris_penawaran(quote_id, baris)
            if keterangan is not None:
                await TenderRepository._tulis_keterangan(quote_id, keterangan)
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="tender_quotes",
                entityID=int(quote_id),
                action="update",
                userID=user_id,
            )
            return {"id": quote_id}
        except Exception as e:
            log_error(f"Error updating tender quote: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def hapus_penawaran(quote_id: int, user_id: int) -> Dict[str, Any]:
        try:
            await database.execute(
                update(tender_quotes_table)
                .where(tender_quotes_table.c.id == quote_id)
                .values(isDelete=True, deletedAt=dt.now(), deletedBy=user_id)
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="tender_quotes",
                entityID=int(quote_id),
                action="delete",
                userID=user_id,
            )
            return {"id": quote_id}
        except Exception as e:
            log_error(f"Error deleting tender quote: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def penawaran_satu(quote_id: int) -> Optional[Dict[str, Any]]:
        baris = await database.fetch_one(
            select(tender_quotes_table).where(
                tender_quotes_table.c.id == quote_id,
                tender_quotes_table.c.isDelete == False,  # noqa: E712
            )
        )
        return dict(baris) if baris else None

    @staticmethod
    async def jumlah_penawaran(tender_id: int) -> int:
        return (
            await database.fetch_val(
                select(func.count())
                .select_from(tender_quotes_table)
                .where(
                    tender_quotes_table.c.tenderID == tender_id,
                    tender_quotes_table.c.isDelete == False,  # noqa: E712
                )
            )
            or 0
        )

    @staticmethod
    async def pemasok_sudah_menawar(tender_id: int, supplier_id: int) -> bool:
        """
        Satu pemasok satu penawaran per tender.

        Dua penawaran dari pemasok yang sama membuat perbandingan menampilkan
        satu nama dua kali dengan angka berbeda — dan yang membacanya tidak
        tahu mana yang berlaku. Revisi dicatat dengan MENGUBAH penawarannya.
        """
        n = await database.fetch_val(
            select(func.count())
            .select_from(tender_quotes_table)
            .where(
                tender_quotes_table.c.tenderID == tender_id,
                tender_quotes_table.c.supplierID == supplier_id,
                tender_quotes_table.c.isDelete == False,  # noqa: E712
            )
        )
        return bool(n)
