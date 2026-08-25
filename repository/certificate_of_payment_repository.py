"""
Penyimpanan Certificate of Payment.

Di sinilah aturan yang benar-benar menjaga uang perusahaan berada:

  * baris yang di-CoP-kan HARUS milik SPK-nya — bukan pekerjaan lain, bukan
    baris karangan;
  * akumulasi volume lintas seluruh CoP tidak boleh melampaui pagu barisnya;
  * harga TIDAK PERNAH diambil dari kiriman layar, selalu dari baris SPK.

Ketiganya ditegakkan DI SINI, bukan di layar. Layar dapat diubah siapa pun
yang membuka peramban; yang menahan angka mengada-ada hanyalah pemeriksaan
di sisi server.
"""

from datetime import datetime as dt
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy import insert, select, update

from utils.database import database
from utils.errors import ErrorCode, app_error, internal_error
from utils.logger_utils import log_error
from models.certificate_of_payment_model import (
    certificate_of_payments_table,
    certificate_of_payment_items_table,
    certificate_of_payment_adjustments_table,
)
from models.purchase_order_model import purchase_orders_table
from models.purchase_order_item_model import purchase_order_items_table


def _d(nilai: Any) -> Decimal:
    """Angka apa pun -> Decimal, tanpa melewati float.

    Volume dan harga dijumlahkan berkali-kali di berkas ini. Lewat float,
    0.1 + 0.2 tidak sama dengan 0.3, dan pagu yang pas terpakai habis dapat
    tampak terlampaui sepersekian satuan — penolakan yang tidak dapat
    dijelaskan kepada yang mengisinya.
    """
    if nilai is None:
        return Decimal("0")
    if isinstance(nilai, Decimal):
        return nilai
    return Decimal(str(nilai))


class CertificateOfPaymentRepository:
    """Simpan & baca Certificate of Payment beserta penjagaan pagunya."""

    # ------------------------------------------------------------------
    # Rantai dokumen & pagu
    # ------------------------------------------------------------------

    @staticmethod
    async def rantai_ids(purchase_order_id: int) -> List[int]:
        """
        SPK induk beserta SELURUH adendum yang sudah disetujui.

        Berbeda dengan `rantai_dokumen` pada purchase order — yang sengaja
        berhenti di dokumen yang diminta karena dipakai untuk MENCETAK —
        pagu justru harus melihat keadaan TERKINI: adendum yang terbit
        kemarin memperbesar pagu hari ini.

        Adendum yang BELUM disetujui tidak ikut. Ia belum menjadi kesepakatan,
        dan volume yang belum disepakati tidak boleh dapat ditagihkan.
        """
        induk = await database.fetch_one(
            """
            SELECT id, parentPurchaseOrderID
            FROM purchase_orders
            WHERE id = :id AND isDelete = 0
            """,
            {"id": purchase_order_id},
        )
        if not induk:
            return []

        induk_id = induk["parentPurchaseOrderID"] or induk["id"]

        adendum = await database.fetch_all(
            """
            SELECT id
            FROM purchase_orders
            WHERE parentPurchaseOrderID = :induk
              AND isDelete = 0
              AND isApproved = 1
            ORDER BY addendumNumber
            """,
            {"induk": induk_id},
        )
        return [induk_id] + [r["id"] for r in adendum]

    @staticmethod
    async def pagu(purchase_order_id: int) -> List[Dict[str, Any]]:
        """
        Keadaan setiap baris pekerjaan pada rantai SPK ini.

        Untuk tiap baris: volume kontraknya (`pagu`), yang sudah
        disertifikasi CoP lain (`terpakai`), dan sisanya.

        CoP yang DIBATALKAN atau DIHAPUS tidak ikut menghitung — volumenya
        kembali tersedia. CoP yang masih draf IKUT: bila tidak, dua orang
        dapat menyiapkan dua CoP yang masing-masing muat tetapi bersama-sama
        melampaui pagunya, dan keduanya lolos.
        """
        ids = await CertificateOfPaymentRepository.rantai_ids(purchase_order_id)
        if not ids:
            return []

        baris = await database.fetch_all(
            select(
                purchase_order_items_table.c.id,
                purchase_order_items_table.c.purchaseOrderID,
                purchase_order_items_table.c.task,
                purchase_order_items_table.c.unit,
                purchase_order_items_table.c.quantity,
                purchase_order_items_table.c.price,
                purchase_order_items_table.c.item_id,
                purchase_order_items_table.c.equipment_id,
                purchase_order_items_table.c.remarks_1,
            ).where(purchase_order_items_table.c.purchaseOrderID.in_(ids))
        )

        terpakai = await database.fetch_all(
            """
            SELECT ci.purchaseOrderItemID AS baris, SUM(ci.quantity) AS jumlah
            FROM certificate_of_payment_items ci
            JOIN certificate_of_payments c
              ON c.id = ci.certificateOfPaymentID
            WHERE c.isDelete = 0
              AND c.status <> 'cancelled'
              AND ci.purchaseOrderItemID IN (
                    SELECT id FROM purchase_order_items
                    WHERE purchaseOrderID IN :ids
              )
            GROUP BY ci.purchaseOrderItemID
            """,
            {"ids": tuple(ids)},
        )
        dipakai = {r["baris"]: _d(r["jumlah"]) for r in terpakai}

        hasil: List[Dict[str, Any]] = []
        for b in baris:
            pagu = _d(b["quantity"])
            sudah = dipakai.get(b["id"], Decimal("0"))
            hasil.append(
                {
                    "purchaseOrderItemID": b["id"],
                    "purchaseOrderID": b["purchaseOrderID"],
                    "task": b["task"],
                    "unit": b["unit"],
                    "itemID": b["item_id"],
                    "equipmentID": b["equipment_id"],
                    "keterangan": b["remarks_1"],
                    "price": _d(b["price"]),
                    "pagu": pagu,
                    "terpakai": sudah,
                    "sisa": pagu - sudah,
                }
            )
        return hasil

    # ------------------------------------------------------------------
    # Penomoran
    # ------------------------------------------------------------------

    @staticmethod
    async def nomor_berikut(purchase_order_id: int) -> int:
        """Urutan CoP berikutnya pada SPK ini (1, 2, 3 ...)."""
        induk = await database.fetch_val(
            """
            SELECT COALESCE(parentPurchaseOrderID, id)
            FROM purchase_orders WHERE id = :id
            """,
            {"id": purchase_order_id},
        )
        terakhir = await database.fetch_val(
            """
            SELECT MAX(number) FROM certificate_of_payments
            WHERE purchaseOrderID = :po
            """,
            {"po": induk or purchase_order_id},
        )
        return int(terakhir or 0) + 1

    #: Angka bulan menjadi angka Romawi.
    #:
    #: Ditulis sebagai daftar, bukan dihitung: bulannya hanya dua belas dan
    #: tidak akan bertambah. Algoritma Romawi umum di sini hanya menambah
    #: sesuatu yang harus dibaca ulang tiap kali orang memeriksa apakah
    #: bulan sembilan benar "IX".
    BULAN_ROMAWI = (
        "", "I", "II", "III", "IV", "V", "VI",
        "VII", "VIII", "IX", "X", "XI", "XII",
    )

    @staticmethod
    async def nomor_dokumen_berikut(project_name: str) -> int:
        """
        Urutan DOKUMEN berikutnya dalam satu proyek.

        Tidak pernah kembali ke 1. Bulan dan tahun pada nomornya hanya
        menerangkan kapan berkasnya terbit; yang membedakan satu dokumen dari
        yang lain adalah angka ini.

        DOKUMEN TERHAPUS TETAP DIHITUNG — `MAX`, bukan `COUNT`. Nomor yang
        sudah pernah terbit tidak boleh dipakai ulang: salinannya mungkin
        sudah beredar, dan dua berkas berbeda bernomor sama adalah persoalan
        yang tidak dapat diselesaikan belakangan.
        """
        terakhir = await database.fetch_val(
            """
            SELECT MAX(documentNumber)
            FROM certificate_of_payments
            WHERE projectName = :proyek
            """,
            {"proyek": project_name or ""},
        )
        return int(terakhir or 0) + 1

    @staticmethod
    def susun_nama(nomor_dokumen: int, project_name: str, tanggal) -> str:
        """
        Nomor CoP: 001-R501-VIII-2026.

        Bulan dan tahun diambil dari TANGGAL DOKUMEN, bukan dari hari ini:
        CoP bertanggal 31 Agustus yang baru sempat dimasukkan tanggal 2
        September harus tetap bernomor VIII — nomornya menerangkan dokumennya,
        bukan kapan orang mengetiknya.
        """
        try:
            bulan = int(getattr(tanggal, "month", 0)) or 0
            tahun = int(getattr(tanggal, "year", 0)) or 0
        except Exception:
            bulan, tahun = 0, 0
        romawi = (
            CertificateOfPaymentRepository.BULAN_ROMAWI[bulan]
            if 1 <= bulan <= 12
            else "-"
        )
        kode = (project_name or "").strip() or "-"
        return f"{nomor_dokumen:03d}-{kode}-{romawi}-{tahun or '-'}"

    # ------------------------------------------------------------------
    # Tulis
    # ------------------------------------------------------------------

    @staticmethod
    async def create(data: Dict[str, Any], items: List[Dict[str, Any]], user_id: int):
        """
        Simpan satu CoP beserta barisnya.

        `items` hanya memuat `purchaseOrderItemID`, `quantity`, dan
        `remarks` — harga diambil sendiri dari SPK-nya di sini.
        """
        try:
            async with database.transaction():
                nomor = data.get("number") or await CertificateOfPaymentRepository.nomor_berikut(
                    data["purchaseOrderID"]
                )

                # Nomor dokumen diambil DI DALAM transaksi, sedekat mungkin
                # dengan penyisipannya. Diambil di controller, dua permintaan
                # yang datang bersamaan membaca angka terakhir yang sama dan
                # keduanya menyusun nama yang sama — lalu yang kedua ditolak
                # kolom `name` yang unik, dengan galat yang tidak menyebut
                # sebabnya.
                nomor_dokumen = data.get(
                    "documentNumber"
                ) or await CertificateOfPaymentRepository.nomor_dokumen_berikut(
                    data.get("projectName") or ""
                )
                nama = data.get("name") or CertificateOfPaymentRepository.susun_nama(
                    nomor_dokumen, data.get("projectName") or "", data["date"]
                )

                cop_id = await database.execute(
                    insert(certificate_of_payments_table).values(
                        name=nama,
                        number=nomor,
                        documentNumber=nomor_dokumen,
                        purchaseOrderID=data["purchaseOrderID"],
                        projectName=data.get("projectName") or "",
                        date=data["date"],
                        periodStart=data.get("periodStart"),
                        periodEnd=data.get("periodEnd"),
                        note=data.get("note"),
                        status="draft",
                        createdBy=user_id,
                        # Diisi di sini, bukan diserahkan ke default kolom:
                        # pustaka `databases` tidak menjalankan default Python
                        # dan yang terkirim menjadi NULL.
                        createdAt=dt.now(),
                    )
                )

                for it in items:
                    await database.execute(
                        insert(certificate_of_payment_items_table).values(
                            certificateOfPaymentID=cop_id,
                            purchaseOrderItemID=it["purchaseOrderItemID"],
                            quantity=it["quantity"],
                            price=it["price"],
                            amount=it["amount"],
                            remarks=it.get("remarks"),
                        )
                    )

                from repository.audit_log_repository import AuditLogRepository

                await AuditLogRepository.record(
                    entity="certificate_of_payments",
                    entityID=cop_id,
                    action="create",
                    userID=user_id,
                )

            # Ringkasan nilai disusun SESUDAH transaksinya selesai: yang
            # dijumlahkan adalah baris yang benar-benar tersimpan, bukan yang
            # baru diantre.
            await CertificateOfPaymentRepository.hitung_ulang_total(cop_id)

            return {"certificateOfPaymentID": cop_id, "name": data["name"], "number": nomor}
        except Exception as e:
            log_error(f"Gagal membuat certificate of payment: {str(e)}")
            return internal_error()

    @staticmethod
    async def ganti_items(cop_id: int, items: List[Dict[str, Any]], user_id: int):
        """Ganti seluruh baris CoP (dipakai saat menyunting)."""
        try:
            async with database.transaction():
                await database.execute(
                    """
                    DELETE FROM certificate_of_payment_items
                    WHERE certificateOfPaymentID = :id
                    """,
                    {"id": cop_id},
                )
                for it in items:
                    await database.execute(
                        insert(certificate_of_payment_items_table).values(
                            certificateOfPaymentID=cop_id,
                            purchaseOrderItemID=it["purchaseOrderItemID"],
                            quantity=it["quantity"],
                            price=it["price"],
                            amount=it["amount"],
                            remarks=it.get("remarks"),
                        )
                    )
            await CertificateOfPaymentRepository.hitung_ulang_total(cop_id)
            return {"message": "Baris certificate of payment diperbarui"}
        except Exception as e:
            log_error(f"Gagal mengganti baris CoP: {str(e)}")
            return internal_error()

    @staticmethod
    async def update_meta(cop_id: int, nilai: Dict[str, Any], user_id: int):
        """Perbarui keterangan CoP (tanggal, periode, catatan)."""
        try:
            if not nilai:
                return {"message": "Tidak ada perubahan"}
            await database.execute(
                update(certificate_of_payments_table)
                .where(certificate_of_payments_table.c.id == cop_id)
                .values(**nilai)
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="certificate_of_payments",
                entityID=cop_id,
                action="update",
                userID=user_id,
            )
            return {"message": "Certificate of payment diperbarui"}
        except Exception as e:
            log_error(f"Gagal memperbarui CoP: {str(e)}")
            return internal_error()

    @staticmethod
    async def set_checked(cop_id: int, checked: bool, user_id: int):
        """
        Tandai CoP sudah/belum diperiksa.

        Mencabut pemeriksaan ikut MENGGUGURKAN persetujuannya — sama seperti
        purchase order, dan karena alasan yang sama: yang menyetujui bertumpu
        pada pemeriksaan yang ternyata ditarik.
        """
        try:
            nilai = (
                {"isChecked": True, "checkedBy": user_id, "checkedAt": dt.now()}
                if checked
                else {
                    "isChecked": False,
                    "checkedBy": None,
                    "checkedAt": None,
                    "isApproved": False,
                    "approvedBy": None,
                    "approvedAt": None,
                    "status": "draft",
                }
            )
            await database.execute(
                update(certificate_of_payments_table)
                .where(certificate_of_payments_table.c.id == cop_id)
                .values(**nilai)
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="certificate_of_payments",
                entityID=cop_id,
                action="set_checked",
                userID=user_id,
            )
            return {"message": "Pemeriksaan diperbarui"}
        except Exception as e:
            log_error(f"Gagal menandai pemeriksaan CoP: {str(e)}")
            return internal_error()

    @staticmethod
    async def approve(cop_id: int, user_id: int):
        """Setujui CoP. Disaring ulang agar dua persetujuan bersamaan tidak lolos keduanya."""
        try:
            await database.execute(
                update(certificate_of_payments_table)
                .where(certificate_of_payments_table.c.id == cop_id)
                .where(certificate_of_payments_table.c.isApproved == False)  # noqa: E712
                .values(
                    isApproved=True,
                    approvedBy=user_id,
                    approvedAt=dt.now(),
                    status="approved",
                )
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="certificate_of_payments",
                entityID=cop_id,
                action="approve",
                userID=user_id,
            )
            return {"message": "Certificate of payment disetujui"}
        except Exception as e:
            log_error(f"Gagal menyetujui CoP: {str(e)}")
            return internal_error()

    @staticmethod
    async def soft_delete(cop_id: int, user_id: int):
        try:
            await database.execute(
                update(certificate_of_payments_table)
                .where(certificate_of_payments_table.c.id == cop_id)
                .values(isDelete=True, deletedBy=user_id, deletedAt=dt.now())
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="certificate_of_payments",
                entityID=cop_id,
                action="delete",
                userID=user_id,
            )
            return {"message": "Certificate of payment dihapus"}
        except Exception as e:
            log_error(f"Gagal menghapus CoP: {str(e)}")
            return internal_error()

    # ------------------------------------------------------------------
    # Baca
    # ------------------------------------------------------------------

    @staticmethod
    async def get_by_id(cop_id: int):
        try:
            baris = await database.fetch_one(
                """
                SELECT c.*,
                       po.name        AS purchaseOrderName,
                       po.purchaseType,
                       -- Pemasok ikut dibaca: lembar periksa menampilkannya
                       -- pada kartu yang sama dengan formulir purchase
                       -- order, dan kartu itu memuat nama beserta alamat.
                       pemasok.name    AS supplierName,
                       pemasok.address AS supplierAddress,
                       pembuat.name   AS createdByName,
                       pemeriksa.name AS checkedByName,
                       penyetuju.name AS approvedByName,
                       -- Jabatan ikut dibaca karena blok tanda tangan
                       -- mencetaknya di bawah nama. Diambil dari kolomnya
                       -- sendiri, BUKAN disimpulkan dari level akses: dua
                       -- orang dapat sama-sama level 4 dengan jabatan
                       -- berbeda, dan menebaknya membuat dokumen resmi
                       -- menyebut jabatan yang salah.
                       pembuat.position   AS createdByPosition,
                       pemeriksa.position AS checkedByPosition,
                       penyetuju.position AS approvedByPosition
                FROM certificate_of_payments c
                JOIN purchase_orders po ON po.id = c.purchaseOrderID
                LEFT JOIN suppliers pemasok ON pemasok.id = po.supplierID
                LEFT JOIN users pembuat   ON pembuat.id   = c.createdBy
                LEFT JOIN users pemeriksa ON pemeriksa.id = c.checkedBy
                LEFT JOIN users penyetuju ON penyetuju.id = c.approvedBy
                WHERE c.id = :id AND c.isDelete = 0
                """,
                {"id": cop_id},
            )
            if not baris:
                return app_error(
                    ErrorCode.NOT_FOUND, "Certificate of payment tidak ditemukan", 404
                )

            items = await database.fetch_all(
                """
                SELECT ci.*, poi.task, poi.unit, poi.quantity AS paguBaris,
                       poi.item_id, poi.equipment_id
                FROM certificate_of_payment_items ci
                JOIN purchase_order_items poi ON poi.id = ci.purchaseOrderItemID
                WHERE ci.certificateOfPaymentID = :id
                ORDER BY ci.id
                """,
                {"id": cop_id},
            )

            hasil = dict(baris)
            hasil["items"] = [dict(i) for i in items]
            hasil["adjustments"] = await CertificateOfPaymentRepository.ambil_penyesuaian(
                cop_id
            )
            return hasil
        except Exception as e:
            log_error(f"Gagal membaca CoP: {str(e)}")
            return internal_error()

    #: Kolom yang boleh dijadikan dasar pengurutan.
    #:
    #: DAFTAR PUTIH, bukan penyaringan karakter. Nama kolom masuk ke dalam
    #: SQL sebagai teks — ia tidak dapat dijadikan parameter — sehingga
    #: apa pun yang lolos dari sini berjalan sebagai SQL. Yang tidak
    #: dikenali diabaikan, bukan ditolak: pengurutan adalah kenyamanan, dan
    #: menggagalkan seluruh daftar karena satu parameter aneh membuat layar
    #: kosong tanpa keterangan.
    URUTAN_BOLEH = {
        "nomor": "c.name",
        "pemasok": "s.name",
        "proyek": "c.projectName",
        "tanggal": "c.date",
        "pembuat": "pembuat.name",
        "nilai": "c.netAmount",
        # Keadaan bukan satu kolom melainkan disimpulkan dari dua penanda.
        # Diurutkan sesuai PERJALANAN dokumennya — draf, diperiksa,
        # disetujui — bukan menurut abjad namanya, karena urutan itulah
        # yang berarti bagi yang membacanya.
        "keadaan": "c.isApproved, c.isChecked",
    }

    @staticmethod
    def _urutan(sort_by: str | None, sort_dir: str | None) -> str:
        kolom = CertificateOfPaymentRepository.URUTAN_BOLEH.get(
            (sort_by or "").strip()
        )
        arah = "ASC" if (sort_dir or "").lower() == "asc" else "DESC"
        if not kolom:
            # Bawaan: yang terbaru di atas. Itulah yang dicari orang saat
            # membuka daftar tanpa memilih urutan apa pun.
            return "c.date DESC, c.id DESC"
        # `c.id` selalu menjadi pemutus terakhir: tanpa itu dua baris dengan
        # tanggal sama dapat bertukar tempat antar halaman, dan satu dokumen
        # muncul dua kali sementara yang lain tidak pernah muncul.
        bagian = ", ".join(f"{k.strip()} {arah}" for k in kolom.split(","))
        return f"{bagian}, c.id DESC"

    @staticmethod
    async def get_all(
        purchase_order_id: int | None = None,
        project_name: str | None = None,
        created_by: int | None = None,
        page: int = 0,
        page_size: int = 20,
        keyword: str | None = None,
        sort_by: str | None = None,
        sort_dir: str | None = None,
        keadaan: str | None = None,
    ):
        """
        Daftar CoP, disaring dan dipenggal halaman.

        PENCARIAN DIKERJAKAN DI SQL, BUKAN DI LAYAR

        Daftar ini dipenggal per halaman, dan menyaring hasil SATU halaman di
        peramban hanya mencari di dua puluh baris yang kebetulan sedang
        terbuka — yang dicari kerap berada di halaman ketiga, dan layar
        menjawab "tidak ada" untuk dokumen yang jelas ada.
        """
        try:
            syarat = ["c.isDelete = 0"]
            params: Dict[str, Any] = {}
            if purchase_order_id:
                syarat.append("c.purchaseOrderID = :po")
                params["po"] = purchase_order_id
            if project_name:
                syarat.append("c.projectName = :proyek")
                params["proyek"] = project_name
            if created_by:
                syarat.append("c.createdBy = :pembuat")
                params["pembuat"] = created_by

            # Keadaan dokumen disaring DI SQL.
            #
            # Ia tidak tersimpan sebagai satu kolom melainkan disimpulkan dari
            # `isChecked`/`isApproved`, dan sebelumnya layar yang menyaringnya
            # sendiri. Itu keliru pada daftar berhalaman: yang disaring hanya
            # dua puluh baris yang kebetulan terbuka, dan `total` yang dipakai
            # pemenggal halaman tetap menghitung SEMUANYA. Beranda ponsel yang
            # membaca angka itu akan menyebut jumlah yang tidak pernah cocok
            # dengan isi layarnya.
            KEADAAN = {
                "draft": "c.isChecked = 0",
                "diperiksa": "c.isChecked = 1 AND c.isApproved = 0",
                "disetujui": "c.isApproved = 1",
            }
            ke = KEADAAN.get((keadaan or "").strip())
            if ke:
                syarat.append(f"({ke})")

            kata = (keyword or "").strip()
            if kata:
                # Empat kolom, karena itulah empat cara orang menyebut satu
                # dokumen yang sama: nomor CoP-nya, nomor SPK-nya, nama
                # proyeknya, atau nama pemasoknya.
                syarat.append(
                    "(c.name LIKE :kata OR po.name LIKE :kata "
                    "OR c.projectName LIKE :kata OR s.name LIKE :kata)"
                )
                params["kata"] = f"%{kata}%"

            where = " AND ".join(syarat)
            # Hitungannya ikut MENGGABUNG purchase_orders — pencariannya
            # menyentuh kolom di sana, dan jumlah yang dihitung tanpa
            # gabungan itu tidak dapat menyaringnya. Halaman terakhir lalu
            # berisi baris kosong karena jumlahnya lebih besar dari isinya.
            total = await database.fetch_val(
                f"""
                SELECT COUNT(*)
                FROM certificate_of_payments c
                JOIN purchase_orders po ON po.id = c.purchaseOrderID
                LEFT JOIN suppliers s ON s.id = po.supplierID
                WHERE {where}
                """,
                params,
            )

            urutan = CertificateOfPaymentRepository._urutan(sort_by, sort_dir)

            params["limit"] = max(1, int(page_size))
            params["offset"] = max(0, int(page)) * max(1, int(page_size))
            baris = await database.fetch_all(
                f"""
                SELECT c.*, po.name AS purchaseOrderName,
                       s.name AS supplierName,
                       pembuat.name AS createdByName
                FROM certificate_of_payments c
                JOIN purchase_orders po ON po.id = c.purchaseOrderID
                LEFT JOIN suppliers s ON s.id = po.supplierID
                LEFT JOIN users pembuat ON pembuat.id = c.createdBy
                WHERE {where}
                ORDER BY {urutan}
                LIMIT :limit OFFSET :offset
                """,
                params,
            )
            return {"total": int(total or 0), "data": [dict(r) for r in baris]}
        except Exception as e:
            log_error(f"Gagal membaca daftar CoP: {str(e)}")
            return internal_error()

    @staticmethod
    async def spk_kandidat(
        project_name: str | None = None,
        keyword: str | None = None,
        batas: int = 50,
    ):
        """
        Purchase order yang MUNGKIN menjadi dasar CoP.

        Disaring di SQL hanya sejauh yang dapat dinyatakan SQL: sudah
        disetujui, belum dihapus, dan bukan adendum (adendum menambah pagu
        pada rantai induknya, bukan membuka rangkaian CoP tersendiri).

        Penyaringan SPK-vs-PO TIDAK dilakukan di sini: jenis dokumen
        ditentukan `_awalan_dokumen`, yang membaca `customData` — logika
        Python yang tidak dapat dipindahkan ke SQL tanpa menyalinnya, dan
        salinan yang tertinggal akan berselisih diam-diam. Controller yang
        menyaringnya.
        """
        try:
            syarat = [
                "po.isDelete = 0",
                "po.isApproved = 1",
                "po.parentPurchaseOrderID IS NULL",
            ]
            params: Dict[str, Any] = {}
            if project_name:
                syarat.append("po.projectName = :proyek")
                params["proyek"] = project_name
            if keyword:
                syarat.append("(po.name LIKE :kata OR po.projectName LIKE :kata)")
                params["kata"] = f"%{keyword}%"

            params["limit"] = max(1, int(batas))
            baris = await database.fetch_all(
                f"""
                SELECT po.id, po.name, po.projectName, po.purchaseType,
                       po.customData, po.date, po.dpp,
                       s.name AS supplierName,
                       -- Alamat ikut dibaca karena layar pengisian
                       -- menampilkan pemasok pada kartu yang sama dengan
                       -- formulir purchase order — dan kartu itu memuat
                       -- alamatnya. Tanpa ini kartunya kehilangan satu
                       -- baris dan berhenti sebangun dengan padanannya.
                       s.address AS supplierAddress
                FROM purchase_orders po
                LEFT JOIN suppliers s ON s.id = po.supplierID
                WHERE {' AND '.join(syarat)}
                ORDER BY po.date DESC, po.id DESC
                LIMIT :limit
                """,
                params,
            )
            return [dict(r) for r in baris]
        except Exception as e:
            log_error(f"Gagal membaca kandidat SPK: {str(e)}")
            return internal_error()

    # ------------------------------------------------------------------
    # Penagihan (hubungan dengan pembelian)
    # ------------------------------------------------------------------

    @staticmethod
    async def tagihan(cop_id: int) -> Dict[str, Any] | None:
        """
        Pembelian AKTIF yang menagihkan CoP ini, bila ada.

        Dibaca dari `purchases`, BUKAN dari penanda pada CoP. Tidak ada
        penanda kedua yang harus dijaga sejalan — dan karena itu pembelian
        yang dihapus membuka kembali CoP-nya dengan sendirinya, tanpa satu
        pun langkah tambahan yang dapat terlupa.
        """
        baris = await database.fetch_one(
            """
            SELECT p.id, p.invoiceName, p.date, p.dpp, p.lastStatus, p.isPaid,
                   p.createdAt, u.name AS createdByName
            FROM purchases p
            LEFT JOIN users u ON u.id = p.createdBy
            WHERE p.certificateOfPaymentID = :cop AND p.isDelete = 0
            LIMIT 1
            """,
            {"cop": cop_id},
        )
        return dict(baris) if baris else None

    @staticmethod
    async def tagihan_banyak(cop_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """
        Keadaan penagihan untuk BANYAK CoP sekaligus.

        Dipakai daftar. Menanyakannya satu per satu berarti dua puluh kueri
        tambahan tiap kali halaman dibuka — dan daftar yang lambat adalah
        daftar yang orang berhenti membukanya.
        """
        if not cop_ids:
            return {}
        baris = await database.fetch_all(
            """
            SELECT certificateOfPaymentID AS cop, id, invoiceName, isPaid
            FROM purchases
            WHERE certificateOfPaymentID IN :ids AND isDelete = 0
            """,
            {"ids": tuple(cop_ids)},
        )
        return {int(r["cop"]): dict(r) for r in baris}

    @staticmethod
    async def siap_tagih(
        keyword: str | None = None,
        batas: int = 30,
        purchase_order_id: int | None = None,
    ) -> List[Dict[str, Any]]:
        """
        CoP yang SUDAH DISETUJUI dan BELUM ditagihkan.

        Dua syarat, dan keduanya perlu:

          * disetujui — nilainya sudah diputuskan dan tidak akan berubah
            lagi; menagihkan yang belum disetujui berarti angka tagihannya
            masih dapat bergeser setelah tagihannya terbit;
          * belum ditagihkan — `LEFT JOIN ... IS NULL`, bukan penanda pada
            CoP, sehingga yang pembeliannya baru saja dihapus muncul lagi di
            sini tanpa perlu dipulihkan tangan.

        `purchase_order_id` mempersempitnya pada SATU SPK. Dipakai formulir
        pembelian untuk bertanya "SPK yang barusan dipilih ini masih punya
        CoP yang belum ditagihkan, tidak?" — pertanyaan yang jawabannya
        harus datang dari kueri yang sama dengan daftar pemilihnya. Kueri
        terpisah untuk maksud yang sama akan berselisih pada perubahan
        aturan berikutnya, dan yang berselisih adalah peringatan yang
        muncul untuk CoP yang tidak ada di daftar pilihannya.
        """
        syarat = ["c.isDelete = 0", "c.isApproved = 1", "p.id IS NULL"]
        params: Dict[str, Any] = {"limit": max(1, int(batas))}
        if purchase_order_id:
            syarat.append("c.purchaseOrderID = :po")
            params["po"] = int(purchase_order_id)
        kata = (keyword or "").strip()
        if kata:
            syarat.append(
                "(c.name LIKE :kata OR c.projectName LIKE :kata "
                "OR po.name LIKE :kata OR s.name LIKE :kata)"
            )
            params["kata"] = f"%{kata}%"

        baris = await database.fetch_all(
            f"""
            SELECT c.id, c.name, c.number, c.projectName, c.date,
                   c.periodStart, c.periodEnd, c.netAmount,
                   po.id   AS purchaseOrderID,
                   po.name AS purchaseOrderName,
                   po.purchaseType, po.ppn, po.pphCode, po.pphTaxObject,
                   po.pphPercentage, po.supplierID,
                   s.name AS supplierName, s.address AS supplierAddress
            FROM certificate_of_payments c
            JOIN purchase_orders po ON po.id = c.purchaseOrderID
            LEFT JOIN suppliers s ON s.id = po.supplierID
            LEFT JOIN purchases p
                   ON p.certificateOfPaymentID = c.id AND p.isDelete = 0
            WHERE {' AND '.join(syarat)}
            ORDER BY c.date DESC, c.id DESC
            LIMIT :limit
            """,
            params,
        )
        return [dict(r) for r in baris]

    @staticmethod
    async def periode_bertindih(
        purchase_order_id: int,
        mulai,
        selesai,
        kecuali_cop_id: int | None = None,
    ) -> List[Dict[str, Any]]:
        """
        CoP lain atas SPK yang SAMA yang periodenya bertindih.

        SYARAT TINDIHNYA

        Dua rentang bertindih bila `mulai <= periodEnd` DAN
        `selesai >= periodStart`. Bentuk ini menangkap seluruh keadaan
        sekaligus — yang baru seluruhnya di dalam yang lama, yang lama di
        dalam yang baru, dan yang saling menimpa sebagian — tanpa satu pun
        cabang tambahan yang dapat tertinggal.

        UJUNG BERTEMU UJUNG IKUT DIHITUNG

        Tanda `<=` dan `>=`, bukan `<` dan `>`. Periode sebelumnya berakhir
        tanggal 12 dan yang ini mulai tanggal 12 berarti pekerjaan tanggal 12
        disertifikasi DUA KALI: batas periode di sini inklusif — tanggal
        akhir adalah hari yang ikut dihitung, bukan penanda berhenti.
        Memakai `<` membuat kasus yang paling sering terjadi justru lolos.

        Yang dikembalikan seluruh yang bertindih, bukan sekadar penanda
        benar/salah: yang mengisi perlu melihat NOMOR dan TANGGAL dokumen
        pembandingnya untuk memutuskan — dan tanpa itu ia harus mencarinya
        sendiri di daftar.
        """
        syarat = [
            "c.isDelete = 0",
            "c.purchaseOrderID = :po",
            "c.periodStart IS NOT NULL",
            "c.periodEnd IS NOT NULL",
            ":mulai <= c.periodEnd",
            ":selesai >= c.periodStart",
        ]
        params: Dict[str, Any] = {
            "po": int(purchase_order_id),
            "mulai": mulai,
            "selesai": selesai,
        }
        # Dokumen yang sedang DISUNTING tidak bertindih dengan dirinya
        # sendiri; tanpa pengecualian ini setiap penyuntingan periode
        # memunculkan peringatan atas dokumen itu juga.
        if kecuali_cop_id:
            syarat.append("c.id <> :kecuali")
            params["kecuali"] = int(kecuali_cop_id)

        baris = await database.fetch_all(
            f"""
            SELECT c.id, c.name, c.number, c.date,
                   c.periodStart, c.periodEnd,
                   c.isChecked, c.isApproved
            FROM certificate_of_payments c
            WHERE {' AND '.join(syarat)}
            ORDER BY c.periodStart ASC, c.id ASC
            """,
            params,
        )
        return [dict(r) for r in baris]

    # ------------------------------------------------------------------
    # Penyesuaian & ringkasan nilai
    # ------------------------------------------------------------------

    @staticmethod
    async def hitung_ulang_total(cop_id: int) -> Dict[str, Any]:
        """
        Susun ulang ringkasan nilai CoP dari barisnya sendiri.

        DIJALANKAN SETIAP KALI baris atau penyesuaiannya berubah, dan
        totalnya DISIMPAN — bukan dihitung saat dibaca. Angka inilah yang
        diteruskan ke pembukuan; menghitungnya ulang saat dibaca membuat
        dokumen yang sudah disetujui dapat berubah nilainya sendiri bila
        harga baris SPK kelak berbeda.
        """
        try:
            kotor = await database.fetch_val(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM certificate_of_payment_items
                WHERE certificateOfPaymentID = :id
                """,
                {"id": cop_id},
            )
            baris = await database.fetch_all(
                """
                SELECT kind, COALESCE(SUM(amount), 0) AS jumlah
                FROM certificate_of_payment_adjustments
                WHERE certificateOfPaymentID = :id
                GROUP BY kind
                """,
                {"id": cop_id},
            )
            per_jenis = {r["kind"]: _d(r["jumlah"]) for r in baris}
            potongan = per_jenis.get("deduction", Decimal("0"))
            tambahan = per_jenis.get("addition", Decimal("0"))
            kotor = _d(kotor)
            bersih = kotor - potongan + tambahan

            await database.execute(
                update(certificate_of_payments_table)
                .where(certificate_of_payments_table.c.id == cop_id)
                .values(
                    grossAmount=kotor,
                    deductionTotal=potongan,
                    additionTotal=tambahan,
                    netAmount=bersih,
                )
            )
            return {
                "grossAmount": kotor,
                "deductionTotal": potongan,
                "additionTotal": tambahan,
                "netAmount": bersih,
            }
        except Exception as e:
            log_error(f"Gagal menghitung ulang total CoP: {str(e)}")
            return internal_error()

    @staticmethod
    async def ambil_penyesuaian(cop_id: int) -> List[Dict[str, Any]]:
        try:
            baris = await database.fetch_all(
                select(certificate_of_payment_adjustments_table)
                .where(
                    certificate_of_payment_adjustments_table.c.certificateOfPaymentID
                    == cop_id
                )
                .order_by(certificate_of_payment_adjustments_table.c.id)
            )
            return [dict(r) for r in baris]
        except Exception as e:
            log_error(f"Gagal membaca penyesuaian CoP: {str(e)}")
            return []

    @staticmethod
    async def ganti_penyesuaian(
        cop_id: int, penyesuaian: List[Dict[str, Any]], user_id: int
    ):
        """
        Ganti SELURUH penyesuaian CoP ini, lalu susun ulang totalnya.

        Diganti seluruhnya, bukan ditambal per baris: layar mengirimkan
        keadaan akhir yang dikehendaki, dan menyamakannya baris demi baris
        di sini hanya menambah jalan bagi keduanya untuk berselisih.
        """
        try:
            async with database.transaction():
                await database.execute(
                    """
                    DELETE FROM certificate_of_payment_adjustments
                    WHERE certificateOfPaymentID = :id
                    """,
                    {"id": cop_id},
                )
                for p in penyesuaian:
                    await database.execute(
                        insert(certificate_of_payment_adjustments_table).values(
                            certificateOfPaymentID=cop_id,
                            kind=p["kind"],
                            category=p["category"],
                            label=p.get("label"),
                            amount=p["amount"],
                            note=p.get("note"),
                        )
                    )

                from repository.audit_log_repository import AuditLogRepository

                await AuditLogRepository.record(
                    entity="certificate_of_payments",
                    entityID=cop_id,
                    action="update_adjustments",
                    userID=user_id,
                )

            return await CertificateOfPaymentRepository.hitung_ulang_total(cop_id)
        except Exception as e:
            log_error(f"Gagal menyimpan penyesuaian CoP: {str(e)}")
            return internal_error()

    # ------------------------------------------------------------------
    # Data untuk pencetakan
    # ------------------------------------------------------------------

    @staticmethod
    async def cop_sebelumnya(purchase_order_id: int, nomor: int):
        """
        Volume per baris yang sudah disertifikasi CoP SEBELUM nomor ini.

        Dibatasi nomor, bukan "semua kecuali yang ini". Dokumen yang sudah
        terbit harus tetap tercetak sama: BAP nomor 2 menyebut "volume
        sebelumnya" menurut keadaan saat ia terbit, dan mencetaknya ulang
        setelah CoP nomor 3 ada tidak boleh mengubah angka itu.
        """
        try:
            ids = await CertificateOfPaymentRepository.rantai_ids(purchase_order_id)
            if not ids:
                return {}
            baris = await database.fetch_all(
                """
                SELECT ci.purchaseOrderItemID AS baris, SUM(ci.quantity) AS jumlah
                FROM certificate_of_payment_items ci
                JOIN certificate_of_payments c
                  ON c.id = ci.certificateOfPaymentID
                WHERE c.isDelete = 0
                  AND c.status <> 'cancelled'
                  AND c.purchaseOrderID = :po
                  AND c.number < :nomor
                GROUP BY ci.purchaseOrderItemID
                """,
                {"po": ids[0], "nomor": nomor},
            )
            return {r["baris"]: _d(r["jumlah"]) for r in baris}
        except Exception as e:
            log_error(f"Gagal membaca CoP sebelumnya: {str(e)}")
            return {}

    @staticmethod
    async def riwayat_pembayaran(purchase_order_id: int, sampai_nomor: int):
        """Seluruh CoP pada SPK ini sampai nomor tertentu — untuk tabel akumulasi."""
        try:
            ids = await CertificateOfPaymentRepository.rantai_ids(purchase_order_id)
            if not ids:
                return []
            baris = await database.fetch_all(
                """
                SELECT number, name, date, grossAmount, netAmount
                FROM certificate_of_payments
                WHERE purchaseOrderID = :po
                  AND isDelete = 0
                  AND status <> 'cancelled'
                  AND number <= :nomor
                ORDER BY number
                """,
                {"po": ids[0], "nomor": sampai_nomor},
            )
            return [dict(r) for r in baris]
        except Exception as e:
            log_error(f"Gagal membaca riwayat pembayaran CoP: {str(e)}")
            return []

    @staticmethod
    async def baris_kontrak(purchase_order_id: int):
        """Seluruh baris pekerjaan pada rantai SPK, beserta dokumen asalnya."""
        try:
            ids = await CertificateOfPaymentRepository.rantai_ids(purchase_order_id)
            if not ids:
                return []
            baris = await database.fetch_all(
                """
                SELECT poi.id, poi.task, poi.unit, poi.quantity, poi.price,
                       poi.remarks_1, poi.purchaseOrderID,
                       po.addendumNumber
                FROM purchase_order_items poi
                JOIN purchase_orders po ON po.id = poi.purchaseOrderID
                WHERE poi.purchaseOrderID IN :ids
                ORDER BY po.addendumNumber IS NOT NULL, po.addendumNumber, poi.id
                """,
                {"ids": tuple(ids)},
            )
            return [dict(r) for r in baris]
        except Exception as e:
            log_error(f"Gagal membaca baris kontrak: {str(e)}")
            return []

    @staticmethod
    async def nilai_kontrak(purchase_order_id: int) -> Decimal:
        """Nilai SPK beserta seluruh adendum yang sudah disetujui."""
        try:
            ids = await CertificateOfPaymentRepository.rantai_ids(purchase_order_id)
            if not ids:
                return Decimal("0")
            nilai = await database.fetch_val(
                """
                SELECT COALESCE(SUM(quantity * price), 0)
                FROM purchase_order_items
                WHERE purchaseOrderID IN :ids
                """,
                {"ids": tuple(ids)},
            )
            return _d(nilai)
        except Exception as e:
            log_error(f"Gagal menghitung nilai kontrak: {str(e)}")
            return Decimal("0")

    @staticmethod
    async def akumulasi_penyesuaian(
        purchase_order_id: int, kecuali_cop_id: int | None = None
    ) -> Dict[str, Decimal]:
        """
        Berapa yang SUDAH dipotong per kategori pada SPK ini.

        Dipakai menjaga pagu uang muka dan retensi: pengembalian uang muka
        seluruh CoP tidak boleh melebihi uang muka yang benar-benar
        dibayarkan, sama seperti volume tidak boleh melebihi volume kontrak.

        `kecuali_cop_id` mengeluarkan CoP yang sedang disunting — angkanya
        sendiri bukan pemakaian orang lain. Tanpa itu, membuka lalu menyimpan
        tanpa mengubah apa pun akan ditolak karena pagunya seolah terpakai
        dua kali.
        """
        try:
            ids = await CertificateOfPaymentRepository.rantai_ids(purchase_order_id)
            if not ids:
                return {}
            params: Dict[str, Any] = {"po": ids[0]}
            saring = ""
            if kecuali_cop_id:
                saring = " AND c.id <> :kecuali"
                params["kecuali"] = kecuali_cop_id

            baris = await database.fetch_all(
                f"""
                SELECT a.category, a.kind, COALESCE(SUM(a.amount), 0) AS jumlah
                FROM certificate_of_payment_adjustments a
                JOIN certificate_of_payments c
                  ON c.id = a.certificateOfPaymentID
                WHERE c.purchaseOrderID = :po
                  AND c.isDelete = 0
                  AND c.status <> 'cancelled'
                  {saring}
                GROUP BY a.category, a.kind
                """,
                params,
            )
            return {
                f"{r['kind']}:{r['category']}": _d(r["jumlah"]) for r in baris
            }
        except Exception as e:
            log_error(f"Gagal membaca akumulasi penyesuaian: {str(e)}")
            return {}
