from sqlalchemy import select, func, or_, and_, insert, update
from utils.database import database
from utils.logger_utils import log_error
from models.purchase_model import purchases_table, purchase_status_table
from models.purchase_order_model import purchase_orders_table
from models.supplier_model import suppliers_table
from models.payment_outgoing_model import payments_outgoing_table
from datetime import date, datetime as dt
from utils.pajak import MASA_PAJAK_AWAL

class PurchaseRepository:
    @staticmethod
    async def create(purchase_data: dict):
        """
        Create a new purchase in the database.
        """
        try:
            query = insert(purchases_table).values(purchase_data)
            purchase_id = await database.execute(query)
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="purchases",
                entityID=purchase_id,
                action="create",
            )
            return purchase_id
        except Exception as e:
            log_error(f"Error creating purchase: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_all(page: int, pageSize: int, filterObject: dict, sortBy: str, sortByDirection: str, keyword: str | None):
        """
        Retrieve a list of purchases from the database.
        """
        if page < 0:
            return {"error": "Page number must be greater than 0", "status": 400}
        
        try:
            offset = (page) * pageSize

            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
            ]

            conditions = [purchases_table.c.isDelete == False]

            # Keyword search conditions
            or_conditions = []
            if keyword is not None and keyword != "":
                or_conditions.append(purchases_table.c.purchaseOrderName.ilike(f"%{keyword}%"))
                or_conditions.append(purchases_table.c.invoiceName.ilike(f"%{keyword}%"))
                or_conditions.append(purchases_table.c.receiptName.ilike(f"%{keyword}%"))
                or_conditions.append(purchases_table.c.taxInvoiceName.ilike(f"%{keyword}%"))
                or_conditions.append(suppliers_table.c.name.ilike(f"%{keyword}%"))
            
            if or_conditions:
                conditions.append(or_(*or_conditions))

            # Due date filter conditions
            due_or_conditions = []
            if filterObject.get("isDue"):
                due_or_conditions.append(purchases_table.c.dueDate <= dt.now().date())
            if filterObject.get("isNotDue"):
                due_or_conditions.append(purchases_table.c.dueDate > dt.now().date())
            
            if due_or_conditions:
                conditions.append(or_(*due_or_conditions))

            # Payment status filter conditions
            payment_or_conditions = []
            if filterObject.get("isPaid"):
                payment_or_conditions.append(purchases_table.c.isPaid == True)
            if filterObject.get("isUnpaid"):
                payment_or_conditions.append(purchases_table.c.isPaid == False)
            
            if payment_or_conditions:
                conditions.append(or_(*payment_or_conditions))

            # Status filter conditions
            status_or_conditions = []
            if filterObject.get("isReady"):
                status_or_conditions.append(purchases_table.c.lastStatus == "ready")
            if filterObject.get("isDraft"):
                status_or_conditions.append(purchases_table.c.lastStatus == "draft")
            
            if status_or_conditions:
                conditions.append(or_(*status_or_conditions))

            # Sort by
            if sortBy == "date":
                order_by = purchases_table.c.date.desc() if sortByDirection == "desc" else purchases_table.c.date.asc()
            elif sortBy == "purchaseOrderName":
                order_by = purchases_table.c.purchaseOrderName.desc() if sortByDirection == "desc" else purchases_table.c.purchaseOrderName.asc()
            elif sortBy == "dueDate":
                order_by = purchases_table.c.dueDate.desc() if sortByDirection == "desc" else purchases_table.c.dueDate.asc()
            elif sortBy == "total":
                order_by = (purchases_table.c.ppn + purchases_table.c.dpp).desc() if sortByDirection == "desc" else (purchases_table.c.ppn + purchases_table.c.dpp).asc()
            elif sortBy == "supplier":
                order_by = suppliers_table.c.name.desc() if sortByDirection == "desc" else suppliers_table.c.name.asc()
            elif sortBy == "invoiceName":
                order_by = purchases_table.c.invoiceName.desc() if sortByDirection == "desc" else purchases_table.c.invoiceName.asc()
            elif sortBy == "project":
                order_by = purchases_table.c.projectName.desc() if sortByDirection == "desc" else purchases_table.c.projectName.asc()
            else:
                order_by = purchases_table.c.date.desc()

            # Tabel purchases hanya menyimpan NAMA purchase order, bukan
            # id-nya. Id diambil lewat sambungan nama agar dokumennya dapat
            # dibuka langsung dari daftar pembelian — tanpa ini, pengguna
            # harus menyalin nomornya lalu mencarinya di halaman lain.
            query = (
                select(
                    *purchases_table.c,
                    *supplier_columns,
                    purchase_orders_table.c.id.label("purchase_order_id"),
                )
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .join(
                    purchase_orders_table,
                    purchases_table.c.purchaseOrderName
                    == purchase_orders_table.c.name,
                    isouter=True,
                )
                .where(*conditions)
                .order_by(order_by)
                .offset(offset)
                .limit(pageSize)
            )
            purchases = await database.fetch_all(query)

            # Count the total number of purchases
            count_query = (
                select(func.count())
                .select_from(purchases_table.join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id))
                .where(*conditions)
            )
            count = await database.fetch_val(count_query)

            # Convert the result
            purchase_result = []
            for purchase in purchases:
                purchase_dict = dict(purchase)
                purchase_dict["supplier"] = {
                    "id": purchase_dict["supplier_id"],
                    "name": purchase_dict["supplier_name"],
                    "address": purchase_dict["supplier_address"],
                    "city": purchase_dict["supplier_city"],
                    "province": purchase_dict["supplier_province"],
                    "prefix": purchase_dict["supplier_prefix"],
                }
                # Remove individual supplier fields
                for field in ["supplier_id", "supplier_name", "supplier_address", "supplier_city", "supplier_province", "supplier_prefix"]:
                    purchase_dict.pop(field, None)
                purchase_result.append(purchase_dict)

            return {"data": purchase_result, "count": count}
        except Exception as e:
            log_error(f"Error fetching purchases: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def check_exists(invoiceName: str, purchaseOrderName: str):
        """
        Check if a purchase with the given invoice name and purchase order name exists.
        """
        try:
            conditions = [
                purchases_table.c.isDelete == False,
                purchases_table.c.invoiceName == invoiceName,
                purchases_table.c.purchaseOrderName == purchaseOrderName
            ]
            
            query = (
                select(func.count())
                .select_from(purchases_table.join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id))
                .where(*conditions)
            )
            count = await database.fetch_val(query)
            return {"exists": count > 0}
        except Exception as e:
            log_error(f"Error checking purchase: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_by_id(purchaseID: int):
        """
        Get a purchase by ID.
        """
        try:
            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
            ]
            # Nama pembuat ikut diambil agar tampilan detail bisa
            # menampilkannya tanpa permintaan tambahan.
            #
            # Impor ditaruh di dalam fungsi: menaruhnya di kepala berkas
            # menambah ketergantungan saat modul dimuat, dan pada sebagian
            # susunan proyek itu memicu impor melingkar sehingga
            # PurchaseRepository gagal terbaca.
            from models.user_model import users_table

            query = (
                select(
                    *purchases_table.c,
                    *supplier_columns,
                    users_table.c.name.label("createdByName"),
                    # Id purchase order disambungkan lewat namanya, sama
                    # seperti pada daftar: tabel purchases hanya menyimpan
                    # nomornya sebagai teks.
                    purchase_orders_table.c.id.label("purchase_order_id"),
                )
                .select_from(
                    purchases_table.join(
                        suppliers_table,
                        purchases_table.c.supplierID == suppliers_table.c.id,
                    ).outerjoin(
                        users_table,
                        purchases_table.c.createdBy == users_table.c.id,
                    ).outerjoin(
                        purchase_orders_table,
                        purchases_table.c.purchaseOrderName
                        == purchase_orders_table.c.name,
                    )
                )
                .where(purchases_table.c.id == purchaseID)
            )
            purchase = await database.fetch_one(query)

            if not purchase:
                return {"error": "Purchase not found", "status": 404}

            purchase_dict = dict(purchase)
            purchase_dict["supplier"] = {
                "id": purchase_dict["supplier_id"],
                "name": purchase_dict["supplier_name"],
                "address": purchase_dict["supplier_address"],
                "city": purchase_dict["supplier_city"],
                "province": purchase_dict["supplier_province"],
                "prefix": purchase_dict["supplier_prefix"],
            }
            # Remove individual supplier fields
            for field in ["supplier_id", "supplier_name", "supplier_address", "supplier_city", "supplier_province", "supplier_prefix"]:
                purchase_dict.pop(field, None)

            return purchase_dict
        except Exception as e:
            log_error(f"Error fetching purchase by ID: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_purchases_by_purchase_order_name(purchase_order_name: str):
        """
        Get purchases by purchase order name.
        """
        try:
            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
            ]

            conditions = [
                purchases_table.c.isDelete == False,
                purchases_table.c.purchaseOrderName == purchase_order_name
            ]

            query = (
                select(*purchases_table.c, *supplier_columns)
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .where(*conditions)
            )

            purchases = await database.fetch_all(query)

            return {"data": purchases}
        except Exception as e:
            log_error(f"Error fetching purchases: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_drafts_by_project(projectName: str):
        """
        Draft pembelian satu proyek, untuk laporan.

        Draft IKUT dihitung sebagai biaya. Ia belum tentu menjadi pembelian,
        tetapi biaya yang belum tercatat justru yang paling berbahaya di
        sini: tanpanya proyek tampak untung padahal tagihannya belum masuk
        semua.

        Aturan yang sama sudah berlaku pada ikhtisar margin seluruh proyek;
        keduanya harus sepakat, karena dua laporan yang memberi angka berbeda
        untuk proyek yang sama merusak kepercayaan pada dua-duanya.

        Draft yang SUDAH DIKONVERSI tidak ikut — pembeliannya sudah terhitung
        sendiri, dan menghitung keduanya berarti biayanya dobel.
        """
        try:
            if not projectName:
                return {"error": "Project name is required", "status": 400}

            rows = await database.fetch_all(
                """
                SELECT d.*, s.name AS supplier_name, s.prefix AS supplier_prefix
                FROM purchase_draft d
                LEFT JOIN suppliers s ON s.id = d.supplierID
                WHERE d.projectName = :proyek
                  AND d.isDelete = 0
                  AND d.purchaseID IS NULL
                ORDER BY d.date DESC
                """,
                {"proyek": projectName},
            )
            return [dict(r) for r in rows]
        except Exception as e:
            log_error(f"Error fetching drafts for project {projectName}: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_by_project(projectName: str):
        """
        Get purchases by project name.
        """
        try:
            if not projectName:
                return {"error": "Project name is required", "status": 400}
            
            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
            ]
            
            conditions = [
                purchases_table.c.projectName == projectName,
                purchases_table.c.isDelete == False
            ]

            query = (
                select(*purchases_table.c, *supplier_columns)
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .where(*conditions)
                .order_by(purchases_table.c.date.desc())
            )
            purchases = await database.fetch_all(query)

            if not purchases:
                return {"error": "No purchases found for this project", "status": 404}

            # Convert the result to a list of dictionaries
            purchase_list = []
            for purchase in purchases:
                purchase_dict = dict(purchase)
                purchase_dict["supplier"] = {
                    "id": purchase_dict["supplier_id"],
                    "name": purchase_dict["supplier_name"],
                    "address": purchase_dict["supplier_address"],
                    "city": purchase_dict["supplier_city"],
                    "province": purchase_dict["supplier_province"],
                    "prefix": purchase_dict["supplier_prefix"],
                }
                # Remove individual supplier fields
                for field in ["supplier_id", "supplier_name", "supplier_address", "supplier_city", "supplier_province", "supplier_prefix"]:
                    purchase_dict.pop(field, None)
                purchase_list.append(purchase_dict)

            return purchase_list
        except Exception as e:
            log_error(f"Error fetching purchase report by project: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    def masa_pajak_efektif():
        """
        Kolom yang menentukan sebuah pembelian masuk MASA PAJAK yang mana.

        `taxPeriod` bila diisi, `date` bila tidak. Ditulis SEKALI di sini dan
        dipakai seluruh kueri PPN.

        Menyalin `COALESCE(taxPeriod, date)` ke tiap kueri akan membuat
        keduanya berselisih pada perubahan berikutnya, dan yang tertinggal
        tidak menimbulkan galat apa pun: hanya satu laporan yang diam-diam
        mengelompokkan menurut tanggal dokumen sementara laporan di
        sebelahnya memakai masa pajaknya. Selisih semacam itu baru ketahuan
        ketika dua angka yang seharusnya sama dibandingkan tangan.

        NULL berarti ikut tanggal dokumen — lihat catatan pada modelnya.
        """
        return func.coalesce(
            purchases_table.c.taxPeriod, purchases_table.c.date
        )

    @staticmethod
    async def get_ppn_report(month: int, year: int):
        """
        Get PPN report for a specific month and year.

        Dikelompokkan menurut MASA PAJAK, bukan tanggal dokumen: faktur
        pajak yang terbit bulan berikutnya dikreditkan pada bulan terbitnya.
        """
        try:
            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
                suppliers_table.c.npwp.label("supplier_npwp")
            ]
            
            conditions = [
                purchases_table.c.isDelete == False,
                purchases_table.c.isInternal == False,
                purchases_table.c.ppn > 0,
                func.extract(
                    "month", PurchaseRepository.masa_pajak_efektif()
                ) == month,
                func.extract(
                    "year", PurchaseRepository.masa_pajak_efektif()
                ) == year,
                # Masa sebelum batas tidak disajikan sama sekali.
                PurchaseRepository.masa_pajak_efektif() >= MASA_PAJAK_AWAL,
            ]

            query = (
                select(*purchases_table.c, *supplier_columns)
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .where(*conditions)
                .order_by(purchases_table.c.date.asc())
            )
            purchases = await database.fetch_all(query)

            if not purchases:
                return {"error": "No PPN purchases found for this period", "status": 404}

            # Convert the result to a list of dictionaries
            purchase_list = []
            for purchase in purchases:
                purchase_dict = dict(purchase)
                purchase_dict["supplier"] = {
                    "id": purchase_dict["supplier_id"],
                    "name": purchase_dict["supplier_name"],
                    "address": purchase_dict["supplier_address"],
                    "city": purchase_dict["supplier_city"],
                    "province": purchase_dict["supplier_province"],
                    "prefix": purchase_dict["supplier_prefix"],
                    "npwp": purchase_dict["supplier_npwp"],
                }
                # Remove individual supplier fields
                for field in ["supplier_id", "supplier_name", "supplier_address", "supplier_city", "supplier_province", "supplier_prefix", "supplier_npwp"]:
                    purchase_dict.pop(field, None)
                purchase_list.append(purchase_dict)

            return purchase_list
        except Exception as e:
            log_error(f"Error fetching PPN report: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_ppn_masukan_kreditable_bulanan(until_year: int, until_month: int):
        """
        Total PPN masukan pembelian yang DAPAT dikreditkan, per bulan.

        Hanya baris ber-PPN, bukan internal, sudah ada nomor faktur pajak —
        sebab yang belum ada fakturnya tidak boleh mengurangi setoran, jadi
        tidak ikut kompensasi antar masa. Dipakai laporan posisi PPN untuk
        menghitung lebih bayar yang berjalan dari masa ke masa.
        """
        try:
            end_date = (
                dt(until_year + 1, 1, 1)
                if until_month == 12
                else dt(until_year, until_month + 1, 1)
            )
            p = purchases_table.c
            # Tanpa `.label()`: kolom agregat ini murni internal, dan uji skema
            # menolak label pada repository ini yang tidak ada di
            # `PurchaseResponse`. Nilainya dibaca lewat posisi kolom.
            # Dikelompokkan menurut MASA PAJAK, sama seperti rinciannya.
            # Bila yang satu memakai masa pajak dan yang lain tanggal
            # dokumen, saldo kompensasinya tidak akan pernah cocok dengan
            # jumlah baris yang ditampilkan di bawahnya.
            masa = PurchaseRepository.masa_pajak_efektif()
            y = func.extract("year", masa)
            m = func.extract("month", masa)
            total = func.coalesce(func.sum(p.dpp * p.ppn / 100), 0)
            query = (
                select(y, m, total)
                .where(
                    p.isDelete == False,
                    p.isInternal == False,
                    p.ppn > 0,
                    p.taxInvoiceName.isnot(None),
                    func.trim(p.taxInvoiceName) != "",
                    masa < end_date,
                    # Kompensasi antar masa hanya dihitung sejak batas.
                    masa >= MASA_PAJAK_AWAL,
                )
                .group_by(y, m)
            )
            rows = await database.fetch_all(query)
            return {(int(r[0]), int(r[1])): float(r[2] or 0) for r in rows}
        except Exception as e:
            log_error(f"Error fetching monthly creditable PPN (purchase): {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_monthly_recap(month: int, year: int):
        try:
            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
                suppliers_table.c.npwp.label("supplier_npwp"),
            ]

            query = (
                select(*purchases_table.c, *supplier_columns)
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .where(
                    func.extract('month', purchases_table.c.date) == month,
                    func.extract('year', purchases_table.c.date) == year,
                    purchases_table.c.isDelete == False
                )
                .order_by(purchases_table.c.date.asc())
            )

            results = await database.fetch_all(query)
            return results
        except Exception as e:
            log_error(f"Error fetching monthly purchase report: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
        
    @staticmethod
    async def get_monthly_ap(month: int, year: int):
        """
            The goal is to determine the purchase invoice on this month and year, and before that (example, the month and year is 1 and 2026, then search sales invoices that is less than "2026-31-01")
            Then left join with the payment received
            if the difference is less than 5 Rupiah, then consider it as paid
            The others that has difference more than 5 Rupiah should be considered as AR
        """
        try:
            
            # Hitung batas akhir bulan
            if month == 12:
                end_date = dt(year + 1, 1, 1)
            else:
                end_date = dt(year, month + 1, 1)


            # Subquery total payment per purchase
            payment_subquery = (
                select(
                    payments_outgoing_table.c.purchaseID.label("purchase_id"),
                    func.coalesce(func.sum(payments_outgoing_table.c.amount), 0).label("total_paid")
                )
                .where(
                    payments_outgoing_table.c.date < end_date,
                    payments_outgoing_table.c.isDelete == False,
                    payments_outgoing_table.c.isApprove == True,
                )
                .group_by(payments_outgoing_table.c.purchaseID)
                .subquery()
            )

            supplier_columns = [
                suppliers_table.c.id.label("supplier_id"),
                suppliers_table.c.name.label("supplier_name"),
                suppliers_table.c.address.label("supplier_address"),
                suppliers_table.c.city.label("supplier_city"),
                suppliers_table.c.province.label("supplier_province"),
                suppliers_table.c.prefix.label("supplier_prefix"),
                suppliers_table.c.npwp.label("supplier_npwp"),
            ]

            # Main query
            query = (
                select(
                    purchases_table.c.id,
                    purchases_table.c.invoiceName,
                    purchases_table.c.receiptName,
                    purchases_table.c.taxInvoiceName,
                    purchases_table.c.purchaseOrderName,
                    purchases_table.c.projectName,
                    purchases_table.c.date,
                    purchases_table.c.dpp,
                    purchases_table.c.pbbkb,
                    purchases_table.c.pphPercentage,
                    purchases_table.c.pphCode,
                    purchases_table.c.ppn,
                    purchases_table.c.pphTaxObject,
                    purchases_table.c.otherValue,
                    purchases_table.c.otherValueNote,
                    func.coalesce(payment_subquery.c.total_paid, 0).label("total_paid"),
                    (
                        (purchases_table.c.ppn * purchases_table.c.dpp / 100 + 
                         purchases_table.c.dpp + purchases_table.c.pbbkb + 
                         purchases_table.c.otherValue - 
                         purchases_table.c.pphPercentage * purchases_table.c.dpp / 100) -
                        func.coalesce(payment_subquery.c.total_paid, 0)
                    ).label("remaining"),
                    *supplier_columns
                )
                .outerjoin(
                    payment_subquery,
                    purchases_table.c.id == payment_subquery.c.purchase_id
                )
                .join(suppliers_table, purchases_table.c.supplierID == suppliers_table.c.id)
                .where(
                    purchases_table.c.date < end_date,
                    purchases_table.c.isDelete == False,
                    purchases_table.c.isInternal == False,
                    #Where the difference is less than 5 Rupiah
                    (purchases_table.c.ppn * purchases_table.c.dpp / 100 + 
                     purchases_table.c.dpp + purchases_table.c.pbbkb + 
                     purchases_table.c.otherValue - 
                     purchases_table.c.pphPercentage * purchases_table.c.dpp / 100) -
                    func.coalesce(payment_subquery.c.total_paid, 0) >= 5
                )
            )

            results = await database.fetch_all(query)

            ap_list = []

            for row in results:
                data = dict(row)
                if data["remaining"] is not None and data["remaining"] > 5:
                    ap_list.append(data)

            return {
                "data": ap_list,
                "count": len(ap_list)
            }

        except Exception as e:
            log_error(f"Error fetching AP report: {str(e)}")
            raise

    @staticmethod
    async def get_frequent_payment_by_supplier_id(supplierID: int):
        # Fetch the most frequent payment number of a supplier
        try:
            query = (
                select(
                    purchases_table.c.bankAccountNumber,
                    purchases_table.c.bankAccountName,
                    purchases_table.c.bankName,
                    func.count(purchases_table.c.bankAccountNumber).label('usage_count')
                )
                .where(purchases_table.c.supplierID == supplierID)
                .group_by(
                    purchases_table.c.bankAccountNumber,
                    purchases_table.c.bankAccountName,
                    purchases_table.c.bankName
                )
                .order_by(func.count(purchases_table.c.bankAccountNumber).desc())
                .limit(1)
            )
            result = await database.fetch_one(query)
            if not result:
                return {"error": "Supplier frequent payment not found", "status": 404}
            return {
                "bankAccountNumber": result.bankAccountNumber,
                "bankAccountName": result.bankAccountName,
                "bankName": result.bankName
            }
        except Exception as e:
            log_error(f"Error fetching frequent payment by supplier ID: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update(purchase_id: int, data: dict, userID: int):
        """
        Ubah isi pembelian.

        Kolom yang boleh diubah DIDAFTAR di sini, bukan diambil apa adanya
        dari muatan permintaan. Menyalin seluruh isi muatan membuat klien
        dapat menulis `isDelete`, `isPaid`, `createdBy`, bahkan `id` —
        cukup dengan menambahkan satu field pada permintaannya.

        `supplierName` dan `supplierAddress` yang ikut dikirim layar sengaja
        TIDAK ada di daftar: keduanya bukan kolom tabel ini, melainkan hasil
        join ke `suppliers` yang dipakai untuk ditampilkan.

        `certificateOfPaymentID` juga TIDAK ada di daftar, dan itu disengaja.
        Ia ditetapkan sekali saat pembelian dibuat, dan penjagaan "satu CoP
        satu tagihan" berjalan pada saat itu. Bila ia dapat diubah belakangan,
        satu pembelian dapat dipindahkan ke CoP lain tanpa melewati penjagaan
        mana pun — dan CoP yang ditinggalkannya menjadi terbuka kembali
        walaupun tagihannya sudah beredar. Memindahkan tagihan dilakukan
        dengan menghapus lalu membuat ulang.
        """
        BOLEH = {
            "invoiceName", "receiptName", "taxInvoiceName", "purchaseOrderName",
            "projectName", "purchaseType", "supplierID", "procurementType",
            "date", "dueDate", "taxPeriod",
            "isInvoiceAttached", "isReceiptAttached", "isTaxInvoiceAttached",
            "isCopAttached", "isCopyPurchaseOrderAttached",
            "dpp", "ppn", "pbbkb", "otherValue", "otherValueNote",
            "pphCode", "pphTaxObject", "pphPercentage",
            "bankName", "bankAccountName", "bankAccountNumber",
            "paymentMethod", "lastStatus", "lastStatusDescription",
        }

        try:
            nilai = {k: v for k, v in (data or {}).items() if k in BOLEH}
            if not nilai:
                return {"error": "No editable field supplied.", "status": 400}

            _sebelum = await database.fetch_one(
                select(purchases_table).where(purchases_table.c.id == purchase_id)
            )
            if not _sebelum:
                return {"error": "Purchase not found", "status": 404}
            if _sebelum["isDelete"]:
                # Dokumen terhapus tidak diubah diam-diam: yang terlihat di
                # layar adalah daftar aktif, jadi perubahan pada baris
                # terhapus tidak akan pernah terlihat siapa pun.
                return {"error": "Purchase already deleted", "status": 400}

            nilai["updatedAt"] = dt.now()
            nilai["updatedBy"] = userID

            await database.execute(
                update(purchases_table)
                .where(purchases_table.c.id == purchase_id)
                .values(**nilai)
            )

            from repository.audit_log_repository import AuditLogRepository

            _sesudah = await database.fetch_one(
                select(purchases_table).where(purchases_table.c.id == purchase_id)
            )
            await AuditLogRepository.record(
                entity="purchases",
                entityID=purchase_id,
                action="update",
                userID=userID,
                changes=AuditLogRepository.diff(
                    dict(_sebelum), dict(_sesudah or {})
                ),
            )
            return {"message": "Purchase updated successfully"}
        except Exception as e:
            log_error(f"Error updating purchase {purchase_id}: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def update_status(purchase_id: int, status_data: dict, userID: int):
        """
        Update purchase status and details.
        """
        try:
            # Keadaan sebelum & sesudah dibandingkan agar nilai lama ikut
            # terekam; tanpa ini audit hanya tahu "diubah", bukan "dari apa".
            _sebelum = await database.fetch_one(
                select(purchases_table).where(purchases_table.c.id == purchase_id)
            )
            update_query = (
                update(purchases_table)
                .where(purchases_table.c.id == purchase_id)
                .values(
                    lastStatus="ready",
                    lastStatusDescription=None,
                    updatedAt=dt.now(),
                    updatedBy=userID,
                    invoiceName=status_data["invoiceName"],
                    receiptName=status_data["receiptName"],
                    taxInvoiceName=status_data["taxInvoiceName"],
                    date=status_data["date"],
                    dueDate=status_data["dueDate"],
                    isCopAttached=status_data["isCopAttached"],
                    isCopyPurchaseOrderAttached=status_data["isCopyPurchaseOrderAttached"],
                    isInvoiceAttached=status_data["isInvoiceAttached"],
                    isReceiptAttached=status_data["isReceiptAttached"],
                    isTaxInvoiceAttached=status_data["isTaxInvoiceAttached"]
                )
            )
            result = await database.execute(update_query)
            if result == 0:
                return {"error": "Purchase not found", "status": 404}
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="purchases",
                entityID=purchase_id,
                action="update_status",
                userID=userID,
                changes=AuditLogRepository.diff(
                    dict(_sebelum) if _sebelum else {},
                    dict(
                        await database.fetch_one(
                            select(purchases_table).where(
                                purchases_table.c.id == purchase_id
                            )
                        )
                        or {}
                    ),
                ),
            )
            
            return {"message": "Purchase status updated successfully"}
        except Exception as e:
            log_error(f"Error updating purchase status: {str(e)}")
            return {"error": "Internal server error.", "status": 500}


    @staticmethod
    async def belum_dibayar(project_name: str = ""):
        """
        Tagihan pembelian yang belum lunas.

        Kelalaian yang paling mahal di sini bukan salah angka, melainkan
        tagihan yang tidak pernah dibuka sama sekali: pemasok menagih, tidak
        ada yang menindaklanjuti, dan yang menemukannya kemudian adalah
        pemasoknya sendiri.

        Yang dihitung SISA, bukan hanya `isPaid`: pembayaran sebagian membuat
        `isPaid` tetap salah tetapi sisanya sudah jauh lebih kecil, dan
        keduanya perlu dibedakan saat menilai mana yang mendesak.

        Toleransi 5 rupiah, sama seperti pada persetujuan pembayaran —
        pembulatan sen membuat sisa satu-dua rupiah yang bukan utang.
        """
        try:
            bayar = (
                select(
                    payments_outgoing_table.c.purchaseID.label("purchase_id"),
                    func.coalesce(
                        func.sum(payments_outgoing_table.c.amount), 0
                    ).label("total_paid"),
                )
                .where(
                    payments_outgoing_table.c.isDelete == False,  # noqa: E712
                    payments_outgoing_table.c.isApprove == True,  # noqa: E712
                )
                .group_by(payments_outgoing_table.c.purchaseID)
                .subquery()
            )

            nilai = (
                purchases_table.c.ppn * purchases_table.c.dpp / 100
                + purchases_table.c.dpp
                + purchases_table.c.pbbkb
                + purchases_table.c.otherValue
                - purchases_table.c.pphPercentage * purchases_table.c.dpp / 100
            )
            sisa = nilai - func.coalesce(bayar.c.total_paid, 0)

            syarat = [
                purchases_table.c.isDelete == False,  # noqa: E712
                sisa > 5,
            ]
            if project_name:
                syarat.append(purchases_table.c.projectName == project_name)

            rows = await database.fetch_all(
                select(
                    purchases_table.c.id,
                    purchases_table.c.invoiceName,
                    purchases_table.c.purchaseOrderName,
                    purchases_table.c.projectName,
                    purchases_table.c.date,
                    purchases_table.c.dueDate,
                    suppliers_table.c.name.label("supplierName"),
                    nilai.label("nilai"),
                    func.coalesce(bayar.c.total_paid, 0).label("dibayar"),
                    sisa.label("sisa"),
                )
                .select_from(
                    purchases_table.outerjoin(
                        bayar, purchases_table.c.id == bayar.c.purchase_id
                    ).outerjoin(
                        suppliers_table,
                        purchases_table.c.supplierID == suppliers_table.c.id,
                    )
                )
                .where(and_(*syarat))
                .order_by(purchases_table.c.dueDate.asc().nullslast())
            )

            hari_ini = date.today()
            hasil = []
            for r in rows:
                d = dict(r)
                jatuh = d.get("dueDate")
                # Sudah lewat tempo DITANDAI di sini, bukan dihitung layar:
                # jam peramban dapat meleset, dan daftar yang menuntut
                # tindakan tidak boleh bergantung padanya.
                d["lewatTempo"] = bool(jatuh and jatuh < hari_ini)
                d["hariTerlambat"] = (
                    (hari_ini - jatuh).days if jatuh and jatuh < hari_ini else 0
                )
                # Dibayar sebagian dibedakan dari yang belum sama sekali:
                # yang pertama sudah ditangani seseorang, yang kedua belum.
                d["sebagian"] = float(d.get("dibayar") or 0) > 0
                hasil.append(d)
            return hasil
        except Exception as e:
            log_error(f"Error listing unpaid purchases: {str(e)}")
            return []
    @staticmethod
    async def update_payment_status(purchaseID: int, isPaid: bool):
        """
        Update the payment status of a purchase.
        """
        try:
            # Keadaan sebelum & sesudah dibandingkan agar nilai lama ikut
            # terekam; tanpa ini audit hanya tahu "diubah", bukan "dari apa".
            _sebelum = await database.fetch_one(
                select(purchases_table).where(purchases_table.c.id == purchaseID)
            )
            query = (
                update(purchases_table)
                .where(purchases_table.c.id == purchaseID)
                .values(isPaid=isPaid)
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Purchase not found", "status": 404}
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="purchases",
                entityID=purchaseID,
                action="update_payment_status",
                changes=AuditLogRepository.diff(
                    dict(_sebelum) if _sebelum else {},
                    dict(
                        await database.fetch_one(
                            select(purchases_table).where(
                                purchases_table.c.id == purchaseID
                            )
                        )
                        or {}
                    ),
                ),
            )

            return {"message": "Payment status updated successfully"}
        except Exception as e:
            log_error(f"Error updating payment status: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def delete(purchaseID: int, userID: int):
        """
        Soft delete a purchase.
        """
        try:
            query = (
                update(purchases_table)
                .where(purchases_table.c.id == purchaseID)
                .values(isDelete=True, deletedAt=dt.now(), deletedBy=userID)
            )
            result = await database.execute(query)
            if result == 0:
                return {"error": "Purchase not found", "status": 404}
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="purchases",
                entityID=purchaseID,
                action="delete",
                userID=userID,
            )

            return {"message": "Purchase deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting purchase: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

class PurchaseStatusRepository:
    @staticmethod
    async def create(status_data: dict):
        """
        Create a new purchase status.
        """
        try:
            query = insert(purchase_status_table).values(status_data)
            purchase_status_id = await database.execute(query)
            
            from repository.audit_log_repository import AuditLogRepository
            
            await AuditLogRepository.record(
                entity="purchases",
                entityID=purchase_status_id,
                action="create",
            )
            return purchase_status_id
        except Exception as e:
            log_error(f"Error creating purchase status: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_by_purchase_id(purchaseID: int):
        """
        Get all statuses for a purchase.
        """
        try:
            query = (
                select(purchase_status_table)
                .where(purchase_status_table.c.purchaseID == purchaseID)
                .order_by(purchase_status_table.c.createdAt.desc())
            )
            statuses = await database.fetch_all(query)
            return [dict(status) for status in statuses]
        except Exception as e:
            log_error(f"Error fetching purchase statuses: {str(e)}")
            return {"error": "Internal server error.", "status": 500}