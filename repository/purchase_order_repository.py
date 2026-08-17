import json
from datetime import datetime as dt
from utils.permission import boleh_menyetujui_sendiri
from utils.errors import app_error, ErrorCode
from sqlalchemy import insert, select, func, update, or_
from sqlalchemy.exc import IntegrityError
from utils.database import database
from models.purchase_order_model import purchase_orders_table
from models.supplier_model import suppliers_table
from models.user_model import users_table
from utils.logger_utils import log_error

# JSON columns that may come back as strings from the driver and should be dicts
_JSON_COLUMNS = ("customData", "billing_requirements")


def _normalize_row(row):
    """Turn a DB row into a plain dict, decoding JSON columns if they came back as strings."""
    if row is None:
        return None
    data = dict(row)
    for col in _JSON_COLUMNS:
        val = data.get(col)
        if isinstance(val, str):
            try:
                data[col] = json.loads(val)
            except (ValueError, TypeError):
                pass
    return data


class PurchaseOrderRepository:
    @staticmethod
    async def kemungkinan_duplikat(
        supplier_id: int, project_name: str, dpp: float, kecuali_id: int = None
    ):
        """
        Dokumen serupa yang dibuat pada HARI YANG SAMA.

        Yang dicari: pemasok sama, proyek sama, dan nilai yang praktis sama.
        Gabungan itu jarang terjadi dua kali dalam sehari secara sengaja —
        dan kalau terjadi, biasanya karena permintaan yang sama dikirim dua
        kali, atau layar yang tidak menjawab lalu ditekan lagi.

        Draf ikut dihitung. Justru draf yang paling sering menggandakan:
        dokumen pertama belum disetujui, sehingga tidak terlihat pada daftar
        yang disaring, lalu dibuat lagi.

        `kecuali_id` untuk mode ubah — dokumen tidak boleh menganggap dirinya
        sendiri sebagai duplikat.
        """
        try:
            nilai = float(dpp or 0)
            if nilai <= 0:
                return None

            # Toleransi seperseribu, bukan sama persis: pembulatan pajak dan
            # pembulatan di layar menghasilkan selisih beberapa rupiah pada
            # dokumen yang sebenarnya identik.
            batas = max(1.0, nilai * 0.001)

            kueri = (
                select(
                    purchase_orders_table.c.id,
                    purchase_orders_table.c.number,
                    purchase_orders_table.c.dpp,
                    purchase_orders_table.c.isApproved,
                    # Tanpa `.label()`: nama label akan dianggap bagian dari
                    # jawaban PurchaseOrderResponse, padahal hasil ini dipakai
                    # sebagai pemeriksaan tersendiri, bukan sebagai dokumen.
                    users_table.c.name,
                )
                .select_from(
                    purchase_orders_table.outerjoin(
                        users_table,
                        purchase_orders_table.c.createdBy == users_table.c.id,
                    )
                )
                .where(purchase_orders_table.c.supplierID == supplier_id)
                .where(purchase_orders_table.c.projectName == project_name)
                .where(purchase_orders_table.c.isDelete == 0)
                .where(func.date(purchase_orders_table.c.createdAt) == func.curdate())
                .where(
                    func.abs(purchase_orders_table.c.dpp - nilai) <= batas
                )
                .order_by(purchase_orders_table.c.id.desc())
                .limit(1)
            )
            if kecuali_id:
                kueri = kueri.where(purchase_orders_table.c.id != kecuali_id)

            baris = await database.fetch_one(kueri)
            if baris is None:
                return None
            return {
                "id": baris["id"],
                "number": baris["number"],
                "dpp": float(baris["dpp"] or 0),
                "isApproved": bool(baris["isApproved"]),
                "pembuat": baris["name"],
            }
        except Exception as e:
            log_error(f"Gagal memeriksa duplikat: {str(e)}")
            return None

    @staticmethod
    async def harga_terakhir(item_id: int, supplier_id: int):
        """
        Harga terakhir barang ini dari pemasok ini.

        Hanya dari dokumen yang SUDAH DISETUJUI. Draf memuat angka yang masih
        dicoba-coba; membandingkan dengan draf berarti membandingkan dengan
        tebakan orang lain, dan kesalahan yang belum sempat dibetulkan justru
        menjadi acuan.

        Mengembalikan `None` bila belum pernah ada — barang baru dari pemasok
        baru tidak punya pembanding, dan itu bukan keadaan yang mencurigakan.
        """
        from models.purchase_order_item_model import purchase_order_items_table as poi

        try:
            kueri = (
                select(
                    poi.c.price,
                    purchase_orders_table.c.date,
                    purchase_orders_table.c.number,
                    poi.c.unit,
                )
                .select_from(
                    poi.join(
                        purchase_orders_table,
                        poi.c.purchaseOrderID == purchase_orders_table.c.id,
                    )
                )
                .where(poi.c.item_id == item_id)
                .where(purchase_orders_table.c.supplierID == supplier_id)
                .where(purchase_orders_table.c.isApproved == 1)
                .where(purchase_orders_table.c.isDelete == 0)
                .where(poi.c.price > 0)
                .order_by(purchase_orders_table.c.date.desc())
                .limit(1)
            )
            baris = await database.fetch_one(kueri)
            if baris is None:
                return None
            return {
                "price": float(baris["price"]),
                "date": baris["date"],
                "number": baris["number"],
                "unit": baris["unit"],
            }
        except Exception as e:
            log_error(f"Gagal membaca harga terakhir: {str(e)}")
            return None

    @staticmethod
    async def get_project_purchase_order_count(project_name: str) -> int:
        """Count non-deleted purchase orders for a specific project."""
        try:
            query = (
                select(func.count())
                .select_from(purchase_orders_table)
                .where(
                    purchase_orders_table.c.projectName == project_name,
                    purchase_orders_table.c.isDelete == False,
                )
            )
            return await database.fetch_val(query) or 0
        except Exception as e:
            log_error(f"Error counting purchase orders for project {project_name}: {str(e)}")
            return 0

    @staticmethod
    async def next_addendum_number(parent_id: int) -> int:
        """
        Urutan adendum berikutnya untuk satu dokumen induk.

        Dihitung dari MAX, bukan COUNT: adendum yang dihapus lunak tetap
        pernah terbit dan nomornya sudah dipegang vendor. Memakai COUNT
        akan menerbitkan `ADD2` untuk kedua kalinya setelah satu adendum
        dihapus.
        """
        n = await database.fetch_val(
            """
            SELECT MAX(addendumNumber)
            FROM purchase_orders
            WHERE parentPurchaseOrderID = :induk
            """,
            {"induk": parent_id},
        )
        return int(n or 0) + 1

    @staticmethod
    async def sisa_volume_induk(parent_id: int) -> dict:
        """
        Volume yang MASIH TERSISA per baris pekerjaan pada satu induk.

        Dihitung dari induk ditambah seluruh adendum yang sudah terbit —
        karena adendum berisi selisih, penjumlahannya langsung menghasilkan
        keadaan sekarang.

        Baris dicocokkan lewat `item_id` bila ada, dan lewat teks
        pekerjaannya bila tidak. Pencocokan teks memang tidak sempurna;
        yang penting ia tidak pernah MELONGGARKAN penjagaan — baris yang
        gagal dicocokkan dianggap baris baru, sehingga pengurangan atasnya
        tetap tertolak karena sisanya nol.
        """
        rows = await database.fetch_all(
            """
            SELECT i.item_id, i.task, SUM(i.quantity) AS volume
            FROM purchase_order_items i
            JOIN purchase_orders po ON po.id = i.purchaseOrderID
            WHERE (po.id = :induk OR po.parentPurchaseOrderID = :induk)
              AND po.isDelete = 0
            GROUP BY i.item_id, i.task
            """,
            {"induk": parent_id},
        )
        sisa: dict = {}
        for r in rows:
            d = dict(r)
            kunci = PurchaseOrderRepository._kunci_baris(d.get("item_id"), d.get("task"))
            sisa[kunci] = sisa.get(kunci, 0) + float(d.get("volume") or 0)
        return sisa

    @staticmethod
    def _kunci_baris(item_id, task) -> str:
        """
        Kunci pencocokan baris antara adendum dan induknya.

        `item_id` didahulukan karena pasti; teks pekerjaan dipakai bila
        tidak ada, diseragamkan spasi dan huruf besarnya agar perbedaan
        pengetikan yang tidak berarti tidak membuat baris dianggap berbeda.
        """
        if item_id:
            return f"id:{item_id}"
        return "task:" + " ".join(str(task or "").split()).lower()

    @staticmethod
    async def periksa_pengurangan(parent_id: int, items: list) -> list[str]:
        """
        Periksa bahwa pengurangan tidak melampaui yang tersisa.

        Kembaliannya daftar masalah; kosong berarti sah. Dikembalikan
        sebagai daftar, bukan melempar pada yang pertama, supaya yang
        mengisi melihat seluruh barisnya sekaligus dan tidak memperbaiki
        satu per satu.

        Sepadan dengan penjagaan pada pinjaman: `debt` tidak boleh turun di
        bawah jumlah yang sudah dibayarkan. Di sini, volume tidak boleh
        turun di bawah nol.
        """
        sisa = await PurchaseOrderRepository.sisa_volume_induk(parent_id)
        masalah: list[str] = []
        for it in items or []:
            v = float(it.get("quantity") or 0)
            if v >= 0:
                continue
            kunci = PurchaseOrderRepository._kunci_baris(
                it.get("item_id"), it.get("task")
            )
            tersedia = sisa.get(kunci, 0)
            if abs(v) > tersedia + 0.0001:
                nama = it.get("task") or f"baris {kunci}"
                masalah.append(
                    f"{nama}: pengurangan {abs(v):g} melebihi sisa {tersedia:g}"
                )
        return masalah

    @staticmethod
    async def rantai_dokumen(purchase_order_id: int) -> list[int]:
        """
        Induk beserta adendum SAMPAI dokumen ini, urut terbitnya.

        Mencetak adendum harus menyertakan seluruh yang mendahuluinya:
        adendum berisi SELISIH, sehingga dibaca sendirian ia tidak
        menyatakan keadaan pekerjaannya. Vendor yang menerima `ADD2` saja
        tidak dapat mengetahui volume yang berlaku.

        Adendum SESUDAHNYA tidak ikut. Lembar yang sudah ditandatangani
        tidak boleh berubah isinya karena ada adendum baru — mencetak ulang
        `ADD1` harus menghasilkan berkas yang sama seperti saat ia terbit.
        """
        ini = await database.fetch_one(
            """
            SELECT id, parentPurchaseOrderID, addendumNumber
            FROM purchase_orders
            WHERE id = :id AND isDelete = 0
            """,
            {"id": purchase_order_id},
        )
        if not ini:
            return []

        induk_id = ini["parentPurchaseOrderID"] or ini["id"]
        # Dokumen induk selalu lebih dulu.
        rantai = [induk_id]

        batas = ini["addendumNumber"]
        if batas is None:
            # Yang diminta adalah induknya sendiri: adendumnya tidak ikut.
            return rantai

        baris = await database.fetch_all(
            """
            SELECT id FROM purchase_orders
            WHERE parentPurchaseOrderID = :induk
              AND isDelete = 0
              AND addendumNumber <= :batas
            ORDER BY addendumNumber ASC
            """,
            {"induk": induk_id, "batas": batas},
        )
        rantai.extend(dict(r)["id"] for r in baris)
        return rantai

    @staticmethod
    async def get_addendums(parent_id: int):
        """Seluruh adendum sebuah dokumen, urut nomornya."""
        rows = await database.fetch_all(
            """
            SELECT id, name, addendumNumber, date, dpp, ppn, isDelete
            FROM purchase_orders
            WHERE parentPurchaseOrderID = :induk AND isDelete = 0
            ORDER BY addendumNumber ASC
            """,
            {"induk": parent_id},
        )
        return [dict(r) for r in rows]

    @staticmethod
    async def get_next_project_sequence(project_name: str) -> int:
        """
        Nomor urut berikutnya untuk satu proyek.

        Dibaca dari kolom `number` (MAX + 1), bukan hasil COUNT dan bukan
        hasil parsing teks: COUNT membuat nomor terpakai ulang setelah ada
        PO dihapus, sedangkan parsing ikut mewarisi nomor global lama.
        Baris terhapus tetap dihitung supaya nomor tidak pernah dobel.
        """
        try:
            query = select(func.max(purchase_orders_table.c.number)).where(
                purchase_orders_table.c.projectName == project_name
            )
            highest = await database.fetch_val(query)
            return (highest or 0) + 1
        except Exception as e:
            log_error(
                f"Error getting next sequence for project {project_name}: {str(e)}"
            )
            return 1

    @staticmethod
    async def get_global_purchase_order_count() -> int:
        """Count all non-deleted purchase orders (used for the running PO number)."""
        try:
            query = (
                select(func.count())
                .select_from(purchase_orders_table)
                .where(purchase_orders_table.c.isDelete == False)
            )
            return await database.fetch_val(query) or 0
        except Exception as e:
            log_error(f"Error counting purchase orders: {str(e)}")
            return 0

    @staticmethod
    async def create(purchase_order_data: dict):
        """Create a new purchase order."""
        try:
            query = insert(purchase_orders_table).values(**purchase_order_data)
            result = await database.execute(query)
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="purchase_orders",
                entityID=result,
                action="create",
            )
            return {"purchase_order_id": result}
        except IntegrityError as e:
            log_error(f"Integrity error while creating purchase order: {str(e.orig)}")
            return {"error": "Internal server error.", "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while creating purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_by_id(purchase_order_id: int):
        """
        Satu purchase order yang belum dihapus.

        Nama DAN jabatan penyetuju ikut diambil karena dokumen mencantumkan
        keduanya pada blok tanda tangan. Yang tersimpan di tabel hanya
        `approvedBy` berupa ID; tanpa join ini, dokumen hanya tahu ADA yang
        menyetujui tetapi tidak tahu siapa — dan blok tanda tangannya tidak
        dapat diisi.
        """
        try:
            # Alias untuk join kedua ke tabel pengguna.
            pemeriksa = users_table.alias("pemeriksa")

            query = (
                select(
                    *purchase_orders_table.c,
                    users_table.c.name.label("approvedByName"),
                    users_table.c.position.label("approvedByPosition"),
                    # Nama pemeriksa, untuk keterangan penelusuran pada
                    # dokumen. Tabel yang sama di-join DUA KALI, sehingga
                    # yang kedua perlu alias sendiri — tanpa itu MySQL
                    # menolak dengan "not unique table/alias".
                    pemeriksa.c.name.label("checkedByName"),
                    # Nama dan alamat pemasok.
                    #
                    # Tabel PO hanya menyimpan `supplierID`. Tanpa join ini,
                    # layar yang memuat dokumen — adendum dan koreksi —
                    # menampilkan isian vendor KOSONG walaupun dokumennya
                    # jelas punya pemasok, dan yang membukanya menyimpulkan
                    # datanya hilang.
                    suppliers_table.c.name.label("supplierName"),
                    suppliers_table.c.address.label("supplierAddress"),
                    suppliers_table.c.npwp.label("supplierNpwp"),
                    suppliers_table.c.prefix.label("supplierPrefix"),
                )
                # Kiri luar: PO yang belum disetujui belum punya `approvedBy`,
                # dan join dalam akan menghilangkannya dari hasil sama sekali.
                .select_from(
                    purchase_orders_table.outerjoin(
                        users_table,
                        purchase_orders_table.c.approvedBy == users_table.c.id,
                    ).outerjoin(
                        pemeriksa,
                        purchase_orders_table.c.checkedBy == pemeriksa.c.id,
                    ).outerjoin(
                        suppliers_table,
                        purchase_orders_table.c.supplierID
                        == suppliers_table.c.id,
                    )
                )
                .where(
                    purchase_orders_table.c.id == purchase_order_id,
                    purchase_orders_table.c.isDelete == False,
                )
            )
            result = await database.fetch_one(query)
            if not result:
                return {"error": "Purchase order not found", "status": 404}
            return _normalize_row(result)
        except Exception as e:
            log_error(f"Unexpected error while fetching purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    # Kolom yang boleh dipakai mengurutkan. Daftar putih ini mencegah nama

    # kolom sembarang ikut masuk ke query.

    SORTABLE = {

        "date": purchase_orders_table.c.date,

        "value": purchase_orders_table.c.dpp,

        "supplier": suppliers_table.c.name,

        "project": purchase_orders_table.c.projectName,

        "name": purchase_orders_table.c.name,

        # Tabel ini tidak punya kolom "status"; yang setara adalah isApproved.
        "status": purchase_orders_table.c.isApproved,

    }


    @staticmethod
    def _order_clause(sortBy: str = None, sortByDirection: str = "desc"):
        """Kolom pengurut; jatuh ke createdAt bila kolomnya tidak dikenal."""
        column = PurchaseOrderRepository.SORTABLE.get(
            sortBy, purchase_orders_table.c.createdAt
        )
        return (
            column.asc()
            if str(sortByDirection).lower() == "asc"
            else column.desc()
        )


    @staticmethod
    async def rekap_proyek(project_name: str):
        """
        Seluruh purchase order sebuah proyek beserta baris barangnya.

        Untuk rekap yang diunduh sebagai Excel. Dikembalikan dalam SATU
        permintaan, bukan satu per dokumen: proyek dengan lima puluh dokumen
        berarti lima puluh permintaan, dan rekapnya menjadi lambat justru pada
        proyek yang paling perlu direkap.

        Dokumen terhapus dikecualikan. Dokumen DRAF tetap disertakan — yang
        membacanya perlu tahu berapa nilai yang belum disahkan, dan itu
        ditandai lewat kolom status, bukan dengan menyembunyikannya.

        Mobilisasi dan demobilisasi ikut dikembalikan sebagaimana tersimpan
        (`remarks_4`, `remarks_5`); layar yang menyusun rekap menjadikannya
        baris tersendiri, sama seperti pada dokumen tercetak.
        """
        try:
            dokumen = await database.fetch_all(
                """
                SELECT po.id, po.date, po.name, po.purchaseType, po.projectName,
                       po.dpp, po.ppn, po.pphPercentage, po.status,
                       po.isApproved, po.parentPurchaseOrderID,
                       -- Nama pemasok datang dari tabel `suppliers`; tabel
                       -- purchase_orders hanya menyimpan `supplierID`.
                       s.name AS supplierName,
                       s.prefix AS supplierPrefix
                FROM purchase_orders po
                LEFT JOIN suppliers s ON s.id = po.supplierID
                WHERE po.projectName = :proyek
                  AND po.isDelete = 0
                ORDER BY po.number ASC
                """,
                {"proyek": project_name},
            )
            if not dokumen:
                return {"purchaseOrders": [], "items": []}

            ids = [d["id"] for d in dokumen]
            tanda = ",".join(f":id{i}" for i in range(len(ids)))
            nilai = {f"id{i}": v for i, v in enumerate(ids)}

            baris = await database.fetch_all(
                f"""
                SELECT i.purchaseOrderID, i.task, i.quantity, i.price, i.unit,
                       i.remarks_1, i.remarks_4, i.remarks_5,
                       mi.description AS itemDescription, mi.sku,
                       me.name AS equipmentName
                FROM purchase_order_items i
                LEFT JOIN master_item mi ON mi.id = i.item_id
                LEFT JOIN master_equipment me ON me.id = i.equipment_id
                WHERE i.purchaseOrderID IN ({tanda})
                ORDER BY i.id ASC
                """,
                nilai,
            )
            return {
                "purchaseOrders": [dict(d) for d in dokumen],
                "items": [dict(b) for b in baris],
            }
        except Exception as e:
            log_error(f"Error building project recap: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_all(
        page: int = 1,
        page_size: int = 10,
        keyword: str = None,
        sortBy: str = None,
        sortByDirection: str = "desc",
        status: str = None,
        purchase_type: str = None,
        project_name: str = None,
        date_from: str = None,
        date_to: str = None,
    ):
        """
        Get purchase orders with pagination (newest first).

        `keyword` mencari pada nomor PO dan nama proyek (tabel ini tidak
        menyimpan nama supplier, hanya supplierID).
        Sebelumnya parameter ini tidak ada padahal controller mengirimnya,
        sehingga daftar PO gagal dimuat.
        """
        try:
            offset = (page - 1) * page_size

            conditions = [purchase_orders_table.c.isDelete == False]
            if keyword:
                pattern = f"%{keyword}%"
                conditions.append(
                    or_(
                        purchase_orders_table.c.name.ilike(pattern),
                        purchase_orders_table.c.projectName.ilike(pattern),
                        # Nama pemasok ikut dicari.
                        #
                        # Yang mencatat tagihan memegang faktur dari pemasok,
                        # bukan nomor purchase order — nomornya justru yang
                        # sedang ia cari. Tanpa ini, satu-satunya jalan adalah
                        # menelusuri daftar halaman demi halaman.
                        #
                        # `suppliers_table` sudah ter-join pada kueri ini,
                        # sehingga tidak ada beban tambahan.
                        suppliers_table.c.name.ilike(pattern),
                    )
                )

            # Join ke suppliers: daftar PO menampilkan nama supplier, dan
            # --- penyaring ---
            #
            # Masing-masing hanya berlaku bila DIISI. Yang kosong tidak
            # menambah kondisi apa pun, sehingga daftar tanpa penyaring tetap
            # menghasilkan kueri yang sama seperti sebelumnya.

            # Status disimpulkan dari `isApproved`, bukan kolom tersendiri.
            #
            # Dokumen hanya punya dua keadaan yang berarti di sini: masih
            # draf, atau sudah disetujui. Yang dibatalkan sudah tersaring
            # lebih dulu lewat `isDelete`.
            if status == "draft":
                conditions.append(purchase_orders_table.c.isApproved == False)
            elif status == "approved":
                conditions.append(purchase_orders_table.c.isApproved == True)

            # Beberapa tipe sekaligus, dipisah koma.
            #
            # "Semua PO mandor" berarti D, 5.1.1, dan 5.1.2 — memilihnya satu
            # per satu berarti tiga kali memuat ulang daftar.
            if purchase_type:
                tipe = [t.strip() for t in str(purchase_type).split(",") if t.strip()]
                if tipe:
                    conditions.append(
                        purchase_orders_table.c.purchaseType.in_(tipe)
                    )

            if project_name:
                conditions.append(
                    purchase_orders_table.c.projectName == project_name
                )

            # Rentang tanggal memakai `date`, BUKAN `createdAt`.
            #
            # Yang dicari saat merekap adalah tanggal dokumennya — yang
            # tercetak dan disepakati vendor — bukan kapan barisnya kebetulan
            # dimasukkan ke sistem. Keduanya kerap berbeda beberapa hari.
            if date_from:
                conditions.append(purchase_orders_table.c.date >= date_from)
            if date_to:
                conditions.append(purchase_orders_table.c.date <= date_to)

            # sebelumnya kolom itu tidak ikut diambil sehingga tampil "?".
            query = (
                select(
                    purchase_orders_table,
                    suppliers_table.c.name.label("supplier_name"),
                    suppliers_table.c.prefix.label("supplier_prefix"),
                )
                .select_from(
                    purchase_orders_table.outerjoin(
                        suppliers_table,
                        purchase_orders_table.c.supplierID == suppliers_table.c.id,
                    )
                )
                .where(*conditions)
                .order_by(PurchaseOrderRepository._order_clause(sortBy, sortByDirection))
                .offset(offset)
                .limit(page_size)
            )
            rows = await database.fetch_all(query)

            # Penghitung memakai SUMBER YANG SAMA dengan kueri datanya.
            #
            # `conditions` memuat syarat nama pemasok, dan syarat itu merujuk
            # `suppliers_table`. Tanpa join yang sama di sini, basis data
            # merangkai silang seluruh baris pemasok — jumlahnya melonjak
            # menjadi kelipatan, sementara daftarnya tetap benar.
            #
            # Bedanya tidak menimbulkan galat: yang salah hanya angka di
            # bawah daftar dan jumlah halamannya.
            count_query = (
                select(func.count())
                .select_from(
                    purchase_orders_table.outerjoin(
                        suppliers_table,
                        purchase_orders_table.c.supplierID
                        == suppliers_table.c.id,
                    )
                )
                .where(*conditions)
            )
            total_count = await database.fetch_val(count_query) or 0

            return {
                "data": [_normalize_row(r) for r in rows],
                "count": total_count,
                "page": page,
                "page_size": page_size,
            }
        except Exception as e:
            log_error(f"Unexpected error while fetching purchase orders: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update(
        purchase_order_id: int,
        fields: dict,
        user_id: int = None,
        user_name: str = None,
    ):
        """
        Ubah purchase order yang BELUM disetujui.

        Draf memang belum mengikat — cap DRAFT pada cetakannya menyatakan itu
        — sehingga membetulkannya bukan pemalsuan, melainkan gunanya tahap
        draf. Tanpa jalur ini yang tersisa hanya dua pilihan buruk: menghapus
        lalu membuat ulang, yang membuat deret nomor proyek berlubang; atau
        menerbitkan yang salah lalu diadendum, yang memakai dokumen resmi
        untuk membetulkan sesuatu yang belum pernah terbit.

        Dokumen yang SUDAH disetujui ditolak di sini. Untuk itu jalurnya
        adendum, dan alasannya tidak berubah: lembar yang dipegang vendor
        tidak boleh berbeda dari yang tersimpan.
        """
        try:
            if not fields:
                return {"message": "No changes"}

            # Keadaan sebelum diubah diambil lebih dulu; setelah update,
            # nilai lamanya sudah tertimpa dan tidak bisa direkam lagi.
            sebelum = await database.fetch_one(
                select(purchase_orders_table).where(
                    purchase_orders_table.c.id == purchase_order_id
                )
            )
            if sebelum is None:
                return app_error(
                    ErrorCode.NOT_FOUND, "Purchase order tidak ditemukan.", 404
                )

            # Ditolak begitu disetujui — di SERVER, bukan cukup dengan
            # menyembunyikan tombolnya. Muatan permintaan dapat disusun
            # sendiri oleh siapa pun yang membuka Network tab.
            sudah = bool(getattr(sebelum, "isApproved", 0)) or str(
                getattr(sebelum, "status", "") or ""
            ).lower() == "approved"
            if sudah:
                return app_error(
                    ErrorCode.FORBIDDEN,
                    "Purchase order yang sudah disetujui tidak dapat diubah. "
                    "Gunakan adendum.",
                    403,
                )

            # Kolom yang menentukan IDENTITAS dokumen tidak boleh berubah.
            #
            # Nomor, pemasok, proyek, dan jenisnya menyusun nomor dokumennya
            # sendiri. Mengubah pemasok bukan koreksi melainkan dokumen lain;
            # yang seperti itu dibatalkan lalu dibuat baru.
            TERKUNCI = (
                "id", "name", "number", "supplierID", "projectName",
                "purchaseType", "isApproved", "approvedBy", "approvedAt",
                "createdBy", "createdAt", "revision",
                "parentPurchaseOrderID", "addendumNumber",
            )
            fields = {k: v for k, v in fields.items() if k not in TERKUNCI}

            # Baris barang dipisahkan dari kolom dokumen.
            #
            # `items` bukan kolom `purchase_orders`; membiarkannya masuk ke
            # `update()` membuat SQLAlchemy menolak seluruh permintaan dengan
            # "Unconsumed column names" — dan pesan itu tidak menyebut bahwa
            # yang salah hanya satu kunci di antara belasan.
            baris_baru = fields.pop("items", None)

            # Kunci yang BUKAN kolom tabel dibuang, bukan diteruskan.
            #
            # Formulir mengirim muatan yang sama seperti saat membuat dokumen,
            # dan sebagian isinya memang tidak pernah menjadi kolom —
            # `projectCode` misalnya, yang hanya dipakai server untuk
            # menyusun nomor.
            kolom_sah = {k.name for k in purchase_orders_table.columns}
            fields = {k: v for k, v in fields.items() if k in kolom_sah}

            if not fields and baris_baru is None:
                return {"message": "No changes"}


            # Menyunting MENCABUT pemeriksaan.
            #
            # Tanpa ini, seseorang dapat meminta pemeriksaan, mengubah
            # harganya, lalu menyetujui — dan tanda pemeriksaan itu menjadi
            # tanda atas isi yang sudah tidak ada.
            #
            # Dicabut diam-diam, bukan ditolak: yang menyunting kerap tidak
            # tahu dokumennya sudah diperiksa, dan menolak permintaannya
            # hanya membuatnya menghubungi orang lain. Layar memberitahukan
            # pencabutannya setelah tersimpan.
            fields.pop("isChecked", None)
            fields.pop("checkedBy", None)
            fields.pop("checkedAt", None)

            sudah_diperiksa = bool(getattr(sebelum, "isChecked", 0))

            query = (
                update(purchase_orders_table)
                .where(purchase_orders_table.c.id == purchase_order_id)
                .values(
                    revision=purchase_orders_table.c.revision + 1,
                    isChecked=False,
                    checkedBy=None,
                    checkedAt=None,
                    **fields,
                )
            )
            await database.execute(query)

            # Baris barang DIGANTI seluruhnya, bukan dicocokkan satu per satu.
            #
            # Yang mengubah dapat menambah, menghapus, dan menukar urutan
            # barisnya sekaligus; mencocokkan berdasarkan id membuat baris
            # yang dihapus lalu ditambah kembali kehilangan kaitannya, dan
            # urutan pada dokumen tercetak berubah tanpa sebab.
            #
            # Dokumen ini belum pernah terbit, sehingga tidak ada apa pun yang
            # merujuk id barisnya.
            if baris_baru is not None:
                from repository.purchase_order_item_repository import (
                    PurchaseOrderItemRepository,
                )

                await PurchaseOrderItemRepository.delete_by_po(purchase_order_id)
                if baris_baru:
                    await PurchaseOrderItemRepository.insert_many(
                        purchase_order_id, baris_baru
                    )

            # Impor lokal agar modul repository tidak saling bergantung
            # saat dimuat.
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="purchase_orders",
                entityID=purchase_order_id,
                action="update",
                userID=user_id,
                userName=user_name,
                changes=AuditLogRepository.diff(
                    dict(sebelum) if sebelum else {}, fields
                ),
            )

            return {
                "message": "Purchase order updated successfully",
                # Layar memberitahukan pencabutan ini.
                #
                # Tanpa penanda, dokumen yang tadinya siap disetujui
                # mendadak menolak disetujui — dan yang menyuntingnya tidak
                # punya cara mengetahui sebabnya.
                "pemeriksaanDicabut": sudah_diperiksa,
            }
        except IntegrityError as e:
            log_error(f"Integrity error while updating purchase order: {str(e.orig)}")
            return {"error": "Internal server error.", "status": 400}
        except Exception as e:
            log_error(f"Unexpected error while updating purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def set_checked(
        purchase_order_id: int,
        checked: bool,
        user_id: int,
        user_level: int | None = None,
        departments: set | None = None,
    ):
        """
        Tandai purchase order sudah atau belum diperiksa.

        Tahap sebelum persetujuan. Pemeriksa membaca isinya — harga, volume,
        spesifikasi; penyetuju memutuskan dokumen itu boleh terbit.
        """
        from utils.permission import (
            _departments,
            boleh_memeriksa,
            boleh_memeriksa_sendiri,
        )

        if checked:
            # Divisi dibaca DI SINI, bukan diambil dari objek pengguna.
            #
            # Objek yang dikembalikan `require()` tidak memuat divisi sama
            # sekali — membacanya dari sana selalu menghasilkan kosong, dan
            # setiap procurement level 3 ditolak tanpa sebab yang terlihat.
            if departments is None:
                departments = await _departments(user_id)

            if not boleh_memeriksa(user_level, departments):
                return app_error(
                    ErrorCode.FORBIDDEN,
                    "Pemeriksaan hanya dapat dilakukan oleh procurement "
                    "level 3, atau level 4 ke atas.",
                    403,
                )

            # Pembuatnya tidak boleh memeriksa sendiri — TERMASUK pemilik.
            #
            # Pemeriksaan justru ada untuk menghadirkan mata kedua;
            # membiarkan pembuatnya memeriksa sendiri membuat tahap ini hanya
            # menambah satu klik tanpa menambah apa pun.
            if not boleh_memeriksa_sendiri(user_level):
                pembuat = await database.fetch_val(
                    select(purchase_orders_table.c.createdBy).where(
                        purchase_orders_table.c.id == purchase_order_id
                    )
                )
                if pembuat is not None and int(pembuat) == int(user_id):
                    return app_error(
                        ErrorCode.SELF_APPROVAL_FORBIDDEN,
                        "Dokumen tidak dapat diperiksa oleh pembuatnya "
                        "sendiri. Mintakan pemeriksaan kepada pengguna lain.",
                        403,
                    )

        try:
            _sebelum = await database.fetch_one(
                select(purchase_orders_table).where(
                    purchase_orders_table.c.id == purchase_order_id
                )
            )

            nilai = (
                {
                    "isChecked": True,
                    "checkedBy": user_id,
                    "checkedAt": dt.now(),
                }
                if checked
                else {
                    # Pemeriksaan dicabut: jejaknya ikut dicabut, dan
                    # persetujuan yang terlanjur ikut gugur.
                    #
                    # Dokumen yang sudah disetujui lalu pemeriksaannya
                    # dibatalkan tidak boleh tetap tercetak sah — yang
                    # menandatanganinya bertumpu pada pemeriksaan yang
                    # ternyata ditarik.
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
                update(purchase_orders_table)
                .where(purchase_orders_table.c.id == purchase_order_id)
                .values(**nilai)
            )

            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="purchase_orders",
                entityID=purchase_order_id,
                action="set_checked",
                userID=user_id,
                changes=AuditLogRepository.diff(
                    dict(_sebelum) if _sebelum else {},
                    dict(
                        await database.fetch_one(
                            select(purchase_orders_table).where(
                                purchase_orders_table.c.id == purchase_order_id
                            )
                        )
                        or {}
                    ),
                ),
            )
            return {"message": "Purchase order check state updated"}
        except Exception as e:
            log_error(f"Error setting purchase order checked: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update_status(
        purchase_order_id: int,
        status: str,
        user_id: int,
        user_level: int | None = None,
    ):
        """
        Update only the status of a purchase order.

        Inilah pintu persetujuan purchase order yang sebenarnya dipakai layar
        — `approve()` di bawah tidak pernah dipanggil dari rute mana pun.
        Karena itu penjagaan persetujuan-sendiri harus ada DI SINI; menaruhnya
        hanya di `approve()` berarti aturannya tidak pernah berlaku.
        """
        # Yang membuat dokumen tidak boleh menyetujuinya sendiri.
        #
        # Dikecualikan untuk level 4 ke atas: keduanya memang berwenang atas
        # seluruh dokumen, dan kerap merekalah satu-satunya yang hadir untuk
        # menyetujui. Pengecualian itu tetap tercatat pada jejak aktivitas.
        if status == "approved" and not boleh_menyetujui_sendiri(user_level):
            pembuat = await database.fetch_val(
                select(purchase_orders_table.c.createdBy).where(
                    purchase_orders_table.c.id == purchase_order_id
                )
            )
            if pembuat is not None and int(pembuat) == int(user_id):
                return app_error(
                    ErrorCode.SELF_APPROVAL_FORBIDDEN,
                    "Dokumen tidak dapat disetujui oleh pembuatnya sendiri. "
                    "Mintakan persetujuan kepada pengguna lain.",
                    403,
                )

        # Dokumen harus SUDAH DIPERIKSA sebelum disetujui.
        #
        # Urutannya bukan formalitas: pemeriksa membaca isinya — harga,
        # volume, spesifikasi — dan penyetuju memutuskan dokumen itu boleh
        # terbit. Menyetujui yang belum diperiksa berarti memutuskan tanpa
        # seorang pun membaca isinya lebih dulu.
        if status == "approved":
            sudah = await database.fetch_val(
                select(purchase_orders_table.c.isChecked).where(
                    purchase_orders_table.c.id == purchase_order_id
                )
            )
            if not sudah:
                return app_error(
                    ErrorCode.VALIDATION,
                    "Dokumen belum diperiksa. Mintakan pemeriksaan lebih "
                    "dulu sebelum disetujui.",
                    400,
                )

        try:
            # Keadaan sebelum & sesudah dibandingkan agar nilai lama ikut
            # terekam; tanpa ini audit hanya tahu "diubah", bukan "dari apa".
            _sebelum = await database.fetch_one(
                select(purchase_orders_table).where(purchase_orders_table.c.id == purchase_order_id)
            )
            nilai = {"status": status}

            # `isApproved`, `approvedBy`, dan `approvedAt` ikut ditulis.
            #
            # Sebelumnya hanya `status` yang berubah, sehingga dokumen yang
            # sudah disetujui di layar tetap punya `isApproved = 0` dan
            # `approvedBy` kosong. Akibatnya blok tanda tangan tidak menyebut
            # siapa pun — dokumennya tercetak sah tetapi tanpa nama penyetuju,
            # dan itu tidak menimbulkan galat apa pun.
            if status == "approved":
                nilai.update(
                    isApproved=True,
                    approvedBy=user_id,
                    approvedAt=dt.now(),
                )
            else:
                # Dibatalkan atau dikembalikan ke draf: jejak persetujuannya
                # ikut dicabut. Menyisakan `approvedBy` pada dokumen yang
                # tidak lagi sah membuat orang yang namanya tercantum tampak
                # menyetujui sesuatu yang sudah ditarik.
                nilai.update(
                    isApproved=False,
                    approvedBy=None,
                    approvedAt=None,
                )

            query = (
                update(purchase_orders_table)
                .where(purchase_orders_table.c.id == purchase_order_id)
                .values(**nilai)
            )
            await database.execute(query)
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="purchase_orders",
                entityID=purchase_order_id,
                action="update_status",
                userID=user_id,
                changes=AuditLogRepository.diff(
                    dict(_sebelum) if _sebelum else {},
                    dict(
                        await database.fetch_one(
                            select(purchase_orders_table).where(
                                purchase_orders_table.c.id == purchase_order_id
                            )
                        )
                        or {}
                    ),
                ),
            )
            
            return {"message": "Purchase order status updated successfully"}
        except Exception as e:
            log_error(f"Unexpected error while updating purchase order status: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def approve(
        purchase_order_id: int, user_id: int, user_level: int | None = None
    ):
        """
        Setujui satu purchase order.

        Yang SUDAH disetujui ditolak. Bukan sekadar merapikan: menyetujui
        ulang menimpa `approvedBy` dan `approvedAt`, sehingga jejak siapa
        yang benar-benar menyetujui dokumen itu hilang — padahal blok tanda
        tangan pada lembar yang dipegang vendor memuat nama penyetuju
        pertama.

        Yang sudah dihapus juga ditolak: menyetujui dokumen terhapus
        menghasilkan keadaan yang tidak berarti apa pun.

        Diperiksa DI SINI, bukan hanya dengan menyembunyikan tombolnya.
        Tombol yang tersembunyi hanya menghalangi yang menekan lewat layar.
        """
        try:
            # Yang membuat dokumen tidak boleh menyetujuinya sendiri.
            #
            # Dikecualikan untuk level 4 ke atas: keduanya memang berwenang atas
            # seluruh dokumen, dan kerap merekalah satu-satunya yang hadir untuk
            # menyetujui. Pengecualian itu tetap tercatat pada jejak aktivitas.
            if not boleh_menyetujui_sendiri(user_level):
                pembuat = await database.fetch_val(
                    select(purchase_orders_table.c.createdBy).where(
                        purchase_orders_table.c.id == purchase_order_id
                    )
                )
                if pembuat is not None and int(pembuat) == int(user_id):
                    return app_error(
                        ErrorCode.SELF_APPROVAL_FORBIDDEN,
                        "Dokumen tidak dapat disetujui oleh pembuatnya "
                        "sendiri. Mintakan persetujuan kepada pengguna lain.",
                        403,
                    )

            keadaan = await database.fetch_one(
                """
                SELECT isApproved, isDelete FROM purchase_orders
                WHERE id = :id
                """,
                {"id": purchase_order_id},
            )
            if not keadaan:
                return {"error": "Purchase order not found", "status": 404}
            if keadaan["isDelete"]:
                return {"error": "Purchase order has been deleted", "status": 400}
            if keadaan["isApproved"]:
                return {
                    "error": "Purchase order is already approved",
                    "status": 409,
                }

            query = (
                update(purchase_orders_table)
                .where(purchase_orders_table.c.id == purchase_order_id)
                # Disaring ulang di sini: bila dua orang menyetujui pada saat
                # yang hampir sama, pemeriksaan di atas dapat lolos keduanya
                # sedangkan syarat ini hanya benar untuk yang pertama.
                .where(purchase_orders_table.c.isApproved == False)  # noqa: E712
                .values(
                    isApproved=True,
                    approvedBy=user_id,
                    approvedAt=dt.now(),
                    status="approved",
                )
            )
            await database.execute(query)
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="purchase_orders",
                entityID=purchase_order_id,
                action="approve",
                userID=user_id,
            )

            return {"message": "Purchase order approved successfully"}
        except Exception as e:
            log_error(f"Unexpected error while approving purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def soft_delete(purchase_order_id: int, user_id: int):
        """
        Hapus lunak satu purchase order.

        Yang SUDAH DISETUJUI ditolak. Dokumen yang disetujui sudah dicetak
        dan dipegang vendor; menghapusnya dari sistem membuat lembar yang
        beredar tidak punya padanan sama sekali — dan tidak ada jejak bahwa
        ia pernah ada.

        Dokumen yang perlu diubah setelah disetujui diselesaikan lewat
        ADENDUM, bukan dengan menghapus lalu membuat ulang.
        """
        """Soft delete a purchase order."""
        try:
            keadaan = await database.fetch_one(
                """
                SELECT isApproved, isDelete FROM purchase_orders
                WHERE id = :id
                """,
                {"id": purchase_order_id},
            )
            if not keadaan:
                return {"error": "Purchase order not found", "status": 404}
            if keadaan["isApproved"]:
                return {
                    "error": "Approved purchase order cannot be deleted",
                    "status": 409,
                }

            query = (
                update(purchase_orders_table)
                .where(purchase_orders_table.c.id == purchase_order_id)
                # Disaring ulang: dokumen yang disetujui di sela pemeriksaan
                # di atas dan perintah ini tetap tidak boleh terhapus.
                .where(purchase_orders_table.c.isApproved == False)  # noqa: E712
                .values(isDelete=True, deletedBy=user_id, deletedAt=dt.now())
            )
            await database.execute(query)
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="purchase_orders",
                entityID=purchase_order_id,
                action="delete",
                userID=user_id,
            )

            return {"message": "Purchase order deleted successfully"}
        except Exception as e:
            log_error(f"Unexpected error while deleting purchase order: {str(e)}")
            return {"error": "Internal server error.", "status": 500}