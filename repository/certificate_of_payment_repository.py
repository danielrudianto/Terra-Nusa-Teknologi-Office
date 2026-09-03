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


def _custom(nilai: Any) -> Dict[str, Any]:
    """
    `customData` sebagai dict, apa pun bentuk simpannya.

    Kolomnya JSON dan SQLAlchemy biasanya sudah mengurainya sendiri, tetapi
    sebagian baris lama tersimpan sebagai TEKS. Yang membaca dengan
    mengandaikan salah satunya akan bekerja pada sebagian dokumen saja — dan
    yang gagal tidak menimbulkan galat, hanya nilai yang lenyap.
    """
    import json

    if isinstance(nilai, str):
        try:
            nilai = json.loads(nilai or "{}")
        except Exception:
            return {}
    return nilai if isinstance(nilai, dict) else {}


def _nama_baris(b: Any) -> str | None:
    """
    Nama pekerjaan sebuah baris SPK, dari mana pun ia berasal.

    Baris jasa menyimpan uraiannya di `task`; baris MATERIAL menunjuk
    `master_item` dan `task`-nya kosong; baris alat menunjuk
    `master_equipment`. Layar dan lembar cetak hanya membaca `task`, sehingga
    sejak beton dilayani CoP seluruh barisnya tampil sebagai "-".

    Urutannya disengaja: `task` lebih dulu, sebab bila seseorang mengisinya
    pada baris bermaterial, yang ia tulis itulah yang dimaksud.
    """
    for kunci in ("task", "itemDescription", "equipmentName"):
        nilai = b[kunci] if kunci in b.keys() else None
        if nilai and str(nilai).strip():
            return str(nilai).strip()
    return None


def _nilai_borongan(custom: Dict[str, Any]) -> Decimal | None:
    """
    Nilai borongan SPK, bila dokumennya memang borongan.

    SPK lump sum menyimpan nilainya di `customData.lumpSumPrice`, sementara
    baris pekerjaannya sengaja berharga NOL — barisnya hanya menyatakan
    uraian lingkupnya. `None` berarti dokumennya bukan borongan dan harga
    barisnya berlaku apa adanya.
    """
    if str(custom.get("rateType") or "").strip().lower() != "lumpsum":
        return None
    return _d(custom.get("lumpSumPrice"))


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
    async def _peta_borongan(ids: List[int]) -> Dict[int, Decimal]:
        """
        Nilai borongan tiap SPK pada rantai, untuk yang memang borongan.

        SATU tempat yang membacanya. `pagu()`, `baris_kontrak()`, dan
        `nilai_kontrak()` sama-sama butuh, dan bila masing-masing membacanya
        sendiri, ketiganya akan berselisih pada perubahan berikutnya — layar
        menyebut satu angka, lembar cetak angka lain, dan pagu uang muka
        angka ketiga.
        """
        if not ids:
            return {}
        rows = await database.fetch_all(
            select(
                purchase_orders_table.c.id,
                purchase_orders_table.c.customData,
            ).where(purchase_orders_table.c.id.in_(ids))
        )
        peta: Dict[int, Decimal] = {}
        for p in rows:
            nilai = _nilai_borongan(_custom(p["customData"]))
            if nilai is not None:
                peta[p["id"]] = nilai
        return peta

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

        # Nama pekerjaan diambil lewat JOIN, bukan dari `task` saja.
        #
        # Baris SPK jasa menyimpan uraiannya di `task`. Baris MATERIAL tidak:
        # ia menunjuk `master_item`, dan `task`-nya kosong — sehingga sejak
        # beton dilayani CoP, seluruh barisnya tampil sebagai "-" di layar
        # pencatatan volume dan di lembar BAP. Orang yang mengisi volume
        # melihat dua kotak tanpa nama dan harus menebak mana yang mana.
        baris = await database.fetch_all(
            """
            SELECT i.id, i.purchaseOrderID, i.task, i.unit, i.quantity,
                   i.price, i.item_id, i.equipment_id, i.remarks_1,
                   mi.description AS itemDescription,
                   me.name        AS equipmentName
            FROM purchase_order_items i
            LEFT JOIN master_item      mi ON mi.id = i.item_id
            LEFT JOIN master_equipment me ON me.id = i.equipment_id
            WHERE i.purchaseOrderID IN :ids
            ORDER BY i.id ASC
            """,
            {"ids": tuple(ids)},
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

        # --- Harga pada SPK BORONGAN ---------------------------------------
        #
        # SPK lump sum menyimpan nilainya di `customData.lumpSumPrice`, dan
        # baris pekerjaannya sengaja berharga NOL — layar pembuatannya memang
        # memaksa `price: 0` begitu jenisnya dipilih borongan.
        #
        # Karena harga CoP diambil dari harga baris SPK, seluruh CoP atas SPK
        # borongan lahir bernilai Rp 0. Tidak ada galat: volumenya sah, pagunya
        # cukup, dan dokumennya tercetak rapi — hanya nilainya nol. Itu lembar
        # yang ditandatangani dan ditagihkan.
        #
        # Nilainya dibagi VOLUME KONTRAK barisnya, bukan dipasang utuh: dengan
        # begitu progres sebagian bekerja sendirinya — separuh volume pada SPK
        # borongan 4 juta menjadi 2 juta, tanpa aturan terpisah.
        borongan = await CertificateOfPaymentRepository._peta_borongan(ids)

        # Berapa baris yang dimiliki tiap SPK — nilai borongan hanya dapat
        # diturunkan ke baris bila barisnya memang satu.
        jumlah_baris: Dict[int, int] = {}
        for b in baris:
            jumlah_baris[b["purchaseOrderID"]] = (
                jumlah_baris.get(b["purchaseOrderID"], 0) + 1
            )

        hasil: List[Dict[str, Any]] = []
        for b in baris:
            pagu = _d(b["quantity"])
            sudah = dipakai.get(b["id"], Decimal("0"))
            harga = _d(b["price"])

            # Borongan tak terbagi: SPK borongan dengan LEBIH DARI SATU baris.
            #
            # Satu nilai untuk seluruh lingkup tidak dapat dipecah ke baris
            # tanpa dasar pembagian, dan mengarang dasarnya berarti mengarang
            # angka yang akan ditagihkan. Ditandai di sini, ditolak dengan
            # sebutan jelas saat CoP disusun — bukan diam-diam bernilai nol.
            tak_terbagi = False
            po_id = b["purchaseOrderID"]
            if po_id in borongan:
                if jumlah_baris.get(po_id, 0) == 1 and pagu > 0:
                    harga = borongan[po_id] / pagu
                else:
                    tak_terbagi = True

            hasil.append(
                {
                    "purchaseOrderItemID": b["id"],
                    "purchaseOrderID": po_id,
                    "task": _nama_baris(b),
                    "unit": b["unit"],
                    "itemID": b["item_id"],
                    "equipmentID": b["equipment_id"],
                    "keterangan": b["remarks_1"],
                    "price": harga,
                    "pagu": pagu,
                    "terpakai": sudah,
                    "sisa": pagu - sudah,
                    "boronganTakTerbagi": tak_terbagi,
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
    async def nomor_dokumen_berikut(supplier_id, project_name: str) -> int:
        """
        Urutan DOKUMEN berikutnya untuk satu VENDOR pada satu PROYEK.

        Diurutkan per (vendor, proyek), bukan per proyek saja: dua vendor
        yang mengerjakan proyek yang sama masing-masing punya deretnya
        sendiri, sehingga nomor 001 milik satu vendor tidak menyerobot nomor
        vendor lain.

        Tidak pernah kembali ke 1 dalam satu (vendor, proyek). Tahun pada
        nomornya hanya menerangkan kapan berkasnya terbit.

        DOKUMEN TERHAPUS TETAP DIHITUNG — `MAX`, bukan `COUNT`. Nomor yang
        sudah pernah terbit tidak boleh dipakai ulang: salinannya mungkin
        sudah beredar, dan dua berkas berbeda bernomor sama adalah persoalan
        yang tidak dapat diselesaikan belakangan.
        """
        terakhir = await database.fetch_val(
            """
            SELECT MAX(documentNumber)
            FROM certificate_of_payments
            WHERE supplierID = :vendor AND projectName = :proyek
            """,
            {"vendor": supplier_id, "proyek": project_name or ""},
        )
        return int(terakhir or 0) + 1

    @staticmethod
    def susun_nama(nomor_dokumen: int, supplier_id, project_name: str, tanggal) -> str:
        """
        Nomor CoP: 002-042-R501-2026.

        Susunannya: [urut 3 digit]-[id vendor 3 digit]-[kode proyek]-[tahun].
        Tidak ada lagi bulan Romawi — yang membedakan dokumen dalam satu
        (vendor, proyek) adalah angka urutnya, dan tahun cukup menerangkan
        kapan ia terbit.

        Id vendor DIPAD tiga digit, sama seperti angka urutnya: 2 menjadi
        042 bukan 42, sehingga nomornya sejajar saat diurutkan dan dibaca.

        Tahun diambil dari TANGGAL DOKUMEN, bukan dari hari ini: CoP
        bertanggal 31 Desember yang baru dimasukkan 2 Januari harus tetap
        bertahun dokumennya, bukan tahun orang mengetiknya.
        """
        try:
            tahun = int(getattr(tanggal, "year", 0)) or 0
        except Exception:
            tahun = 0
        try:
            vid = int(supplier_id)
        except (TypeError, ValueError):
            vid = 0
        kode = (project_name or "").strip() or "-"
        return f"{nomor_dokumen:03d}-{vid:03d}-{kode}-{tahun or '-'}"

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
                supplier_id = data.get("supplierID")
                nomor_dokumen = data.get(
                    "documentNumber"
                ) or await CertificateOfPaymentRepository.nomor_dokumen_berikut(
                    supplier_id, data.get("projectName") or ""
                )
                nama = data.get("name") or CertificateOfPaymentRepository.susun_nama(
                    nomor_dokumen,
                    supplier_id,
                    data.get("projectName") or "",
                    data["date"],
                )

                cop_id = await database.execute(
                    insert(certificate_of_payments_table).values(
                        name=nama,
                        number=nomor,
                        documentNumber=nomor_dokumen,
                        purchaseOrderID=data["purchaseOrderID"],
                        supplierID=supplier_id,
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

            # `nama`, BUKAN `data["name"]`.
            #
            # Nama dokumen disusun DI DALAM fungsi ini — pemanggilnya tidak
            # pernah mengirimkannya, dan memang tidak boleh: nomor dokumennya
            # harus diambil di dalam transaksi supaya dua permintaan yang
            # bersamaan tidak menyusun nama yang sama.
            #
            # Membacanya kembali dari `data` melempar KeyError, dan lemparan
            # itu terjadi SESUDAH transaksinya berhasil disimpan — sehingga
            # dokumennya benar-benar tercatat sementara layar menerima galat
            # 500. Yang menekan simpan lalu mencobanya lagi, dan tiap
            # percobaan menambah satu CoP.
            return {
                "certificateOfPaymentID": cop_id,
                "name": nama,
                "number": nomor,
                "documentNumber": nomor_dokumen,
            }
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
    async def bap_approve(cop_id: int, approve: bool, user_id: int):
        """
        Setujui / batalkan persetujuan BAP — GERBANG PERTAMA.

        Ini yang membuka pengisian harga: sebelum BAP disetujui, tidak ada
        nilai rupiah yang boleh disentuh. Membatalkannya (approve=False)
        MENGGUGURKAN seluruh tahap sesudahnya — pembuatan CoP dan
        persetujuannya bertumpu pada progres yang ternyata ditarik kembali,
        sama seperti mencabut pemeriksaan pada purchase order.
        """
        try:
            nilai = (
                {
                    "isBapApproved": True,
                    "bapApprovedBy": user_id,
                    "bapApprovedAt": dt.now(),
                }
                if approve
                else {
                    "isBapApproved": False,
                    "bapApprovedBy": None,
                    "bapApprovedAt": None,
                    # Tahap-tahap sesudahnya ikut gugur.
                    "isCopCreated": False,
                    "copCreatedBy": None,
                    "copCreatedAt": None,
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
                action="approve_bap" if approve else "cabut_bap",
                userID=user_id,
            )
            return {"message": "Persetujuan BAP diperbarui"}
        except Exception as e:
            log_error(f"Gagal menyetujui BAP CoP: {str(e)}")
            return internal_error()

    @staticmethod
    async def set_checked(cop_id: int, checked: bool, user_id: int):
        """
        Tandai CoP DIBUAT / batalkan pembuatannya (tahap harga & potongan).

        Namanya `set_checked` dipertahankan agar rute & pemanggilnya tetap,
        tetapi tahap ini kini adalah PEMBUATAN CoP: yang menstempelnya adalah
        pembuat CoP (`copCreatedBy`), bukan lagi pemeriksa. Membatalkannya
        MENGGUGURKAN persetujuan CoP — yang menyetujui bertumpu pada nilai
        yang ternyata ditarik.
        """
        try:
            nilai = (
                {"isCopCreated": True, "copCreatedBy": user_id, "copCreatedAt": dt.now()}
                if checked
                else {
                    "isCopCreated": False,
                    "copCreatedBy": None,
                    "copCreatedAt": None,
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
            return {"message": "Pembuatan CoP diperbarui"}
        except Exception as e:
            log_error(f"Gagal menandai pembuatan CoP: {str(e)}")
            return internal_error()

    @staticmethod
    async def approve(cop_id: int, user_id: int):
        """Setujui CoP — GERBANG TERAKHIR. Disaring ulang agar dua persetujuan bersamaan tidak lolos keduanya."""
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
                       pembuat.name      AS createdByName,
                       penyetujuBap.name AS bapApprovedByName,
                       pembuatCop.name   AS copCreatedByName,
                       penyetuju.name    AS approvedByName,
                       -- Jabatan ikut dibaca karena blok tanda tangan
                       -- mencetaknya di bawah nama. Diambil dari kolomnya
                       -- sendiri, BUKAN disimpulkan dari level akses: dua
                       -- orang dapat sama-sama level 4 dengan jabatan
                       -- berbeda, dan menebaknya membuat dokumen resmi
                       -- menyebut jabatan yang salah.
                       pembuat.position      AS createdByPosition,
                       penyetujuBap.position AS bapApprovedByPosition,
                       pembuatCop.position   AS copCreatedByPosition,
                       penyetuju.position    AS approvedByPosition
                FROM certificate_of_payments c
                JOIN purchase_orders po ON po.id = c.purchaseOrderID
                LEFT JOIN suppliers pemasok ON pemasok.id = po.supplierID
                LEFT JOIN users pembuat      ON pembuat.id      = c.createdBy
                LEFT JOIN users penyetujuBap ON penyetujuBap.id = c.bapApprovedBy
                LEFT JOIN users pembuatCop   ON pembuatCop.id   = c.copCreatedBy
                LEFT JOIN users penyetuju    ON penyetuju.id    = c.approvedBy
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
        # Keadaan bukan satu kolom melainkan disimpulkan dari tiga penanda.
        # Diurutkan sesuai PERJALANAN dokumennya — draf, BAP disetujui, CoP
        # dibuat, CoP disetujui — bukan menurut abjad namanya, karena urutan
        # itulah yang berarti bagi yang membacanya.
        "keadaan": "c.isApproved, c.isCopCreated, c.isBapApproved",
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
            # tiga penanda tahap, dan sebelumnya layar yang menyaringnya
            # sendiri. Itu keliru pada daftar berhalaman: yang disaring hanya
            # dua puluh baris yang kebetulan terbuka, dan `total` yang dipakai
            # pemenggal halaman tetap menghitung SEMUANYA. Beranda ponsel yang
            # membaca angka itu akan menyebut jumlah yang tidak pernah cocok
            # dengan isi layarnya.
            #
            # Empat tahap perjalanan dokumen:
            #   draft         belum disetujui BAP-nya
            #   bap           BAP disetujui, CoP belum dibuat (menunggu harga)
            #   dibuat        CoP dibuat, belum disetujui
            #   disetujui     CoP disetujui — siap ditagih
            KEADAAN = {
                "draft": "c.isBapApproved = 0",
                "bap": "c.isBapApproved = 1 AND c.isCopCreated = 0",
                "dibuat": "c.isCopCreated = 1 AND c.isApproved = 0",
                "disetujui": "c.isApproved = 1",
                # Alias lama tetap dikenali agar tautan/keping penyaring yang
                # tersimpan tidak mendadak kosong: "diperiksa" kini berarti
                # tahap "dibuat".
                "diperiksa": "c.isCopCreated = 1 AND c.isApproved = 0",
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
                   c.isBapApproved, c.isCopCreated, c.isApproved
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
        """
        Seluruh CoP pada SPK ini sampai nomor tertentu — untuk tabel akumulasi.

        Dicari pada SELURUH RANTAI SPK, bukan hanya SPK induknya. CoP yang
        melekat pada adendum tetap pembayaran atas pekerjaan yang sama, dan
        akumulasi yang melewatkannya menyatakan jumlah yang lebih kecil
        daripada yang benar-benar sudah dibayarkan — persis pada tabel yang
        dipakai memastikan tidak ada pembayaran ganda.
        """
        try:
            ids = await CertificateOfPaymentRepository.rantai_ids(purchase_order_id)
            if not ids:
                return []
            baris = await database.fetch_all(
                """
                SELECT number, name, date, grossAmount, netAmount
                FROM certificate_of_payments
                WHERE purchaseOrderID IN :ids
                  AND isDelete = 0
                  AND status <> 'cancelled'
                  AND number <= :nomor
                ORDER BY number
                """,
                {"ids": tuple(ids), "nomor": sampai_nomor},
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
                       poi.item_id, poi.equipment_id,
                       mi.description AS itemDescription,
                       me.name        AS equipmentName,
                       po.addendumNumber
                FROM purchase_order_items poi
                JOIN purchase_orders po ON po.id = poi.purchaseOrderID
                LEFT JOIN master_item      mi ON mi.id = poi.item_id
                LEFT JOIN master_equipment me ON me.id = poi.equipment_id
                WHERE poi.purchaseOrderID IN :ids
                ORDER BY po.addendumNumber IS NOT NULL, po.addendumNumber, poi.id
                """,
                {"ids": tuple(ids)},
            )

            # Harga & nama diselaraskan dengan `pagu()`.
            #
            # Lembar BAP membaca dari sini, layar pencatatan volume dari
            # `pagu()`. Bila keduanya menurunkan harga borongan dan nama baris
            # dengan cara berbeda, angka di layar dan angka di lembar yang
            # ditandatangani akan berbeda — dan tidak ada yang membandingkannya.
            borongan = await CertificateOfPaymentRepository._peta_borongan(ids)
            jumlah_baris: Dict[int, int] = {}
            for r in baris:
                jumlah_baris[r["purchaseOrderID"]] = (
                    jumlah_baris.get(r["purchaseOrderID"], 0) + 1
                )

            hasil = []
            for r in baris:
                d = dict(r)
                d["task"] = _nama_baris(r)
                po_id = r["purchaseOrderID"]
                pagu = _d(r["quantity"])
                if po_id in borongan and jumlah_baris.get(po_id, 0) == 1 and pagu > 0:
                    d["price"] = borongan[po_id] / pagu
                hasil.append(d)
            return hasil
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
            # Dijumlahkan PER DOKUMEN, bukan sekali atas seluruh rantai.
            #
            # SPK borongan tidak punya harga baris — nilainya di
            # `customData.lumpSumPrice` — sehingga `SUM(quantity * price)`
            # atas SPK borongan menghasilkan NOL. Dan nilai kontrak bukan
            # angka yang berhenti di lembar cetak: pagu uang muka dan pagu
            # retensi dihitung sebagai persentase DARINYA, jadi nol di sini
            # berarti uang muka dan retensi ikut nol tanpa pernah menyebut
            # alasannya.
            #
            # Per dokumen, sebab satu rantai boleh bercampur: induk borongan
            # dengan adendum harga satuan, atau sebaliknya.
            per_po = await database.fetch_all(
                """
                SELECT purchaseOrderID AS po,
                       COALESCE(SUM(quantity * price), 0) AS nilai
                FROM purchase_order_items
                WHERE purchaseOrderID IN :ids
                GROUP BY purchaseOrderID
                """,
                {"ids": tuple(ids)},
            )
            borongan = await CertificateOfPaymentRepository._peta_borongan(ids)

            total = Decimal("0")
            terhitung = set()
            for r in per_po:
                po_id = r["po"]
                terhitung.add(po_id)
                total += borongan[po_id] if po_id in borongan else _d(r["nilai"])

            # SPK borongan yang barisnya belum tercatat sama sekali tetap
            # punya nilai — nilainya tidak pernah berasal dari barisnya.
            for po_id, nilai in borongan.items():
                if po_id not in terhitung:
                    total += nilai

            return total
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
