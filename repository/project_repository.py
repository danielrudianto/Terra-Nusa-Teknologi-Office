from typing import Any, Dict, Optional
from sqlalchemy import select, insert, update, func, or_, and_
from sqlalchemy.exc import IntegrityError
from datetime import datetime as dt

from utils.database import database
from utils.logger_utils import log_error
from models.project_model import projects_table, project_contracts_table


def _ekspresi_nilai():
    """
    Nominal dokumen = DPP + PPN.

    Tidak disimpan sebagai kolom: nilainya selalu dapat dihitung dari `dpp`
    dan `ppn` yang sudah ada di baris yang sama. Menyimpannya berarti dua
    tempat harus selalu sepakat, dan cepat atau lambat salah satunya
    diperbarui tanpa yang lain.
    """
    c = project_contracts_table.c
    return c.dpp + (c.dpp * c.ppn / 100)


def _nilai_kontrak_subquery():
    """
    Jumlah nilai kontrak per proyek, hanya baris yang belum dihapus.

    Dipakai sebagai subquery, bukan dihitung di Python setelah data diambil:
    daftar proyek memakai paginasi, sehingga menghitung di Python berarti
    mengambil seluruh baris kontrak setiap kali halaman dibuka.
    """
    return (
        select(
            project_contracts_table.c.projectID.label("pid"),
            # Nilai dokumen dihitung, bukan dibaca dari kolom: `value` sudah
            # tidak ada sebagai kolom. Ekspresinya dipakai di beberapa tempat,
            # jadi disimpan di satu fungsi agar rumusnya tidak bercabang.
            func.coalesce(func.sum(_ekspresi_nilai()), 0).label("total"),
            func.coalesce(func.sum(project_contracts_table.c.dpp), 0).label("dpp"),
            func.count(project_contracts_table.c.id).label("jumlah"),
        )
        .where(project_contracts_table.c.isDelete == False)  # noqa: E712
        .group_by(project_contracts_table.c.projectID)
        .subquery()
    )


class ProjectRepository:
    # ---- Proyek -----------------------------------------------------------

    @staticmethod
    async def create(data: dict, user_id: int) -> Dict[str, Any]:
        try:
            query = insert(projects_table).values(
                **data,
                createdAt=dt.now(),
                createdBy=user_id,
                isDelete=False,
            )
            project_id = await database.execute(query)

            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="projects", entityID=project_id, action="create"
            )
            return {"message": "Project created successfully", "project_id": project_id}
        except IntegrityError:
            # Satu-satunya batasan unik di tabel ini adalah `code`.
            return {"error": "PROJECT_CODE_EXISTS", "status": 409}
        except Exception as e:
            log_error(f"Error creating project: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_by_id(project_id: int):
        agg = _nilai_kontrak_subquery()
        query = (
            select(
                projects_table,
                func.coalesce(agg.c.total, 0).label("contractValue"),
                func.coalesce(agg.c.dpp, 0).label("contractDpp"),
                func.coalesce(agg.c.jumlah, 0).label("contractCount"),
            )
            .select_from(
                projects_table.outerjoin(agg, agg.c.pid == projects_table.c.id)
            )
            .where(
                projects_table.c.id == project_id,
                projects_table.c.isDelete == False,  # noqa: E712
            )
        )
        return await database.fetch_one(query)

    @staticmethod
    async def get_by_code(code: str):
        query = select(projects_table).where(
            func.upper(projects_table.c.code) == (code or "").strip().upper(),
            projects_table.c.isDelete == False,  # noqa: E712
        )
        return await database.fetch_one(query)

    @staticmethod
    async def get_all(
        keyword: Optional[str] = None,
        isActive: Optional[bool] = None,
        isCancelled: Optional[bool] = None,
        page: int = 1,
        pageSize: int = 10,
        sortBy: Optional[str] = None,
        sortByDirection: str = "asc",
        isRetention: Optional[bool] = None,
        keadaan: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            agg = _nilai_kontrak_subquery()
            syarat = [projects_table.c.isDelete == False]  # noqa: E712
            if keyword:
                pola = f"%{keyword}%"
                syarat.append(
                    or_(
                        projects_table.c.code.like(pola),
                        projects_table.c.name.like(pola),
                    )
                )
            # Dibandingkan dengan `is not None`, bukan kebenaran nilainya:
            # `isActive=False` adalah penyaringan yang sah dan tidak boleh
            # terbaca sebagai "tidak menyaring".
            if isActive is not None:
                syarat.append(projects_table.c.isActive == isActive)
            if isCancelled is not None:
                syarat.append(projects_table.c.isCancelled == isCancelled)
            if isRetention is not None:
                syarat.append(projects_table.c.isRetention == isRetention)

            # Saringan keadaan berupa DAFTAR, bukan satu nilai.
            #
            # Layar menampilkan proyek berjalan saja, lalu menambahkan
            # keadaan lain satu per satu — "termasuk tunggu retensi",
            # "termasuk selesai". Itu pertanyaan ATAU, dan tidak dapat
            # dinyatakan oleh tiga penanda boolean yang saling DAN.
            #
            # Nama keadaan yang tidak dikenal DIABAIKAN, bukan menggugurkan
            # permintaannya: daftar yang kosong karena satu salah ketik lebih
            # sukar dikenali daripada daftar yang kurang satu keadaan.
            if keadaan:
                pilihan = {
                    k.strip().lower()
                    for k in str(keadaan).split(",")
                    if k.strip()
                }
                cabang = []
                if "berjalan" in pilihan:
                    cabang.append(
                        and_(
                            projects_table.c.isActive == True,  # noqa: E712
                            projects_table.c.isCancelled == False,  # noqa: E712
                            projects_table.c.isRetention == False,  # noqa: E712
                        )
                    )
                if "retensi" in pilihan:
                    cabang.append(
                        and_(
                            projects_table.c.isCancelled == False,  # noqa: E712
                            projects_table.c.isRetention == True,  # noqa: E712
                        )
                    )
                if "selesai" in pilihan:
                    cabang.append(
                        and_(
                            projects_table.c.isActive == False,  # noqa: E712
                            projects_table.c.isCancelled == False,  # noqa: E712
                        )
                    )
                if "batal" in pilihan:
                    cabang.append(
                        projects_table.c.isCancelled == True  # noqa: E712
                    )

                # Seluruhnya tidak dikenal: diperlakukan seperti tanpa
                # saringan, bukan seperti "tidak ada yang cocok".
                if cabang:
                    syarat.append(or_(*cabang))

            kolom = {
                "code": projects_table.c.code,
                "name": projects_table.c.name,
                "isActive": projects_table.c.isActive,
                "isCancelled": projects_table.c.isCancelled,
                "startDate": projects_table.c.startDate,
                "contractValue": func.coalesce(agg.c.total, 0),
            }
            urut = kolom.get(sortBy or "code", projects_table.c.code)
            urut = urut.desc() if sortByDirection == "desc" else urut.asc()

            dasar = projects_table.outerjoin(agg, agg.c.pid == projects_table.c.id)

            total = await database.fetch_val(
                select(func.count()).select_from(projects_table).where(and_(*syarat))
            )

            rows = await database.fetch_all(
                select(
                    projects_table,
                    func.coalesce(agg.c.total, 0).label("contractValue"),
                func.coalesce(agg.c.dpp, 0).label("contractDpp"),
                    func.coalesce(agg.c.jumlah, 0).label("contractCount"),
                )
                .select_from(dasar)
                .where(and_(*syarat))
                .order_by(urut)
                .limit(pageSize)
                .offset((max(page, 1) - 1) * pageSize)
            )
            return {"data": [dict(r) for r in rows], "count": total or 0}
        except Exception as e:
            log_error(f"Error listing projects: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def punya_anak(project_id: int) -> int:
        """Berapa proyek yang menjadikan proyek ini induknya."""
        return await database.fetch_val(
            select(func.count())
            .select_from(projects_table)
            .where(
                projects_table.c.parentProjectID == project_id,
                projects_table.c.isDelete == False,  # noqa: E712
            )
        ) or 0

    @staticmethod
    async def keluarga(project_id: int):
        """
        Induk dan anak-anak sebuah proyek, dalam SEKALI baca masing-masing.

        Dipakai layar proyek untuk memberi tahu bahwa proyek yang sedang
        dibuka bukan berdiri sendiri. Tanpa keterangan itu, yang membukanya
        melihat proyek berpembelian tanpa penjualan — atau sebaliknya — dan
        menyimpulkan datanya rusak, padahal pasangannya ada di proyek lain.

        Yang dikembalikan secukupnya untuk ditampilkan dan ditautkan: id,
        kode, nama, dan keadaannya. Nilai kontrak sengaja TIDAK diikutkan —
        ia perlu subkueri tersendiri, dan yang ingin melihatnya tinggal
        membuka proyeknya.
        """
        kolom = (
            projects_table.c.id,
            projects_table.c.code,
            projects_table.c.name,
            projects_table.c.isActive,
            projects_table.c.isCancelled,
            projects_table.c.isRetention,
        )

        anak = await database.fetch_all(
            select(*kolom)
            .where(
                projects_table.c.parentProjectID == project_id,
                projects_table.c.isDelete == False,  # noqa: E712
            )
            .order_by(projects_table.c.code)
        )

        induk_id = await ProjectRepository.induk_dari(project_id)
        induk = None
        if induk_id:
            induk = await database.fetch_one(
                select(*kolom).where(
                    projects_table.c.id == induk_id,
                    projects_table.c.isDelete == False,  # noqa: E712
                )
            )

        return {
            "induk": dict(induk) if induk else None,
            "anak": [dict(r) for r in anak],
        }

    @staticmethod
    async def induk_dari(project_id: int):
        """Id induk sebuah proyek; None bila ia berdiri sendiri."""
        return await database.fetch_val(
            select(projects_table.c.parentProjectID).where(
                projects_table.c.id == project_id
            )
        )

    @staticmethod
    async def count_documents(code: str) -> int:
        """
        Berapa dokumen yang sudah memakai kode proyek ini.

        Kode disimpan sebagai TEKS pada dokumen, bukan tautan ke baris ini —
        `purchases.projectName`, `purchase_orders.projectName`, dan
        seterusnya. Mengubah kodenya tidak ikut memperbarui dokumen lama:
        yang lama tetap menyebut kode lama, sehingga laporan per proyek
        terpecah menjadi dua tanpa ada yang menyadarinya.

        Karena itu penggantian hanya diizinkan selama belum ada dokumen yang
        memakainya — cukup untuk membetulkan salah ketik, tanpa memutus
        jejak yang sudah terbit.
        """
        from models.purchase_draft_model import purchase_draft_table
        from models.purchase_model import purchases_table
        from models.purchase_order_model import purchase_orders_table
        from models.reimbursement_model import reimbursements_table
        from models.sales_invoice_model import sales_invoice_tables

        total = 0
        for tabel in (
            purchases_table,
            purchase_orders_table,
            purchase_draft_table,
            reimbursements_table,
            sales_invoice_tables,
        ):
            n = await database.fetch_val(
                select(func.count()).select_from(tabel).where(
                    tabel.c.projectName == code
                )
            )
            total += int(n or 0)
        return total

    @staticmethod
    async def update(project_id: int, values: dict, user_id: int) -> Dict[str, Any]:
        try:
            _sebelum = await database.fetch_one(
                select(projects_table).where(projects_table.c.id == project_id)
            )
            if _sebelum is None:
                return {"error": "Project not found", "status": 404}

            values = {**values, "updatedAt": dt.now(), "updatedBy": user_id}
            await database.execute(
                update(projects_table)
                .where(projects_table.c.id == project_id)
                .where(projects_table.c.isDelete == False)  # noqa: E712
                .values(**values)
            )

            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="projects",
                entityID=project_id,
                action="update",
                changes=AuditLogRepository.diff(dict(_sebelum), values),
            )
            return {"message": "Project updated successfully", "project_id": project_id}
        except Exception as e:
            log_error(f"Error updating project: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def soft_delete(project_id: int, user_id: int) -> Dict[str, Any]:
        try:
            await database.execute(
                update(projects_table)
                .where(projects_table.c.id == project_id)
                .values(isDelete=True, deletedAt=dt.now(), deletedBy=user_id)
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="projects", entityID=project_id, action="delete"
            )
            return {"message": "Project deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting project: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    # ---- Kontrak ----------------------------------------------------------

    @staticmethod
    async def list_contracts(project_id: int):
        query = (
            select(
                project_contracts_table,
                _ekspresi_nilai().label("value"),
            )
            .where(
                project_contracts_table.c.projectID == project_id,
                project_contracts_table.c.isDelete == False,  # noqa: E712
            )
            .order_by(project_contracts_table.c.date.asc())
        )
        return await database.fetch_all(query)

    @staticmethod
    async def ringkasan_margin(page: int = 1, page_size: int = 10):
        """
        Ikhtisar margin seluruh proyek, satu baris per proyek.

        DIJUMLAHKAN DI BASIS DATA, bukan di layar.

        Laporan satu proyek yang sudah ada menarik empat kumpulan baris utuh
        — pembelian, draft, reimbursement, faktur — lalu menjumlahkannya di
        peramban. Untuk satu proyek itu wajar. Dipakai untuk tabel seluruh
        proyek, jumlah kuerinya tumbuh mengikuti jumlah proyeknya: lima
        puluh proyek berarti dua ratus kueri, dan puluhan ribu baris dikirim
        ke peramban hanya untuk menjadi satu angka per baris.

        Di sini setiap sumber dijumlahkan lebih dulu dengan `GROUP BY`, lalu
        disambungkan ke proyeknya. Yang dikirim hanya sebesar jumlah proyek
        pada halaman itu.

        Nilai kontrak memakai **DPP**, bukan nominal kotor — mengikuti
        laporan per proyek. Membandingkan biaya (yang DPP) dengan kontrak
        yang sudah termasuk PPN membuat margin setiap proyek tampak lebih
        besar daripada sebenarnya.

        Proyek yang MASIH BERJALAN didahulukan: di situlah marginnya masih
        dapat diperbaiki. Yang sudah selesai tetap dapat dilihat pada
        halaman berikutnya.
        """
        try:
            # Halaman dikunci maksimum sepuluh. Ini bukan sekadar pilihan
            # tampilan: tiap baris berasal dari empat penjumlahan, dan
            # membuka batasnya mengembalikan persoalan yang justru hendak
            # dihindari.
            page = max(1, int(page or 1))
            page_size = min(10, max(1, int(page_size or 10)))
            offset = (page - 1) * page_size

            total = await database.fetch_val(
                "SELECT COUNT(*) FROM projects WHERE isDelete = 0"
            )

            baris = await database.fetch_all(
                """
                SELECT
                    p.id,
                    p.code,
                    p.name,
                    p.isActive,
                    p.isCancelled,
                    -- Masa retensi; layar margin menyaringnya seperti daftar
                    -- proyek, dan tanpa kolom ini keadaannya tidak terbaca.
                    p.isRetention,
                    COALESCE(k.kontrak, 0)        AS kontrak,
                    COALESCE(b.beli, 0)           AS beli,
                    COALESCE(b.beli_internal, 0)  AS beli_internal,
                    COALESCE(d.draft, 0)          AS draft,
                    COALESCE(r.reimburse, 0)      AS reimburse,
                    COALESCE(si.tertagih, 0)      AS tertagih
                FROM projects p
                LEFT JOIN (
                    SELECT projectID, SUM(dpp) AS kontrak
                    FROM project_contracts
                    WHERE isDelete = 0
                    GROUP BY projectID
                ) k ON k.projectID = p.id
                LEFT JOIN (
                    SELECT projectName,
                           SUM(dpp) AS beli,
                           SUM(CASE WHEN isInternal = 1 THEN dpp ELSE 0 END)
                               AS beli_internal
                    FROM purchases
                    WHERE isDelete = 0
                    GROUP BY projectName
                ) b ON b.projectName = p.code
                LEFT JOIN (
                    SELECT projectName, SUM(dpp) AS draft
                    FROM purchase_draft
                    WHERE isDelete = 0
                    GROUP BY projectName
                ) d ON d.projectName = p.code
                LEFT JOIN (
                    -- Nilai reimbursement ada di BARISNYA, bukan di kepalanya.
                    --
                    -- `reimbursements` hanya menyimpan meta dokumen; nominalnya
                    -- tersebar pada `reimbursement_items`. Menjumlahkan dari
                    -- tabel kepala gagal dengan "Unknown column 'amount'".
                    SELECT rh.projectName, SUM(ri.amount) AS reimburse
                    FROM reimbursements rh
                    JOIN reimbursement_items ri
                      ON ri.reimbursementID = rh.id
                    WHERE rh.isDelete = 0
                    GROUP BY rh.projectName
                ) r ON r.projectName = p.code
                LEFT JOIN (
                    -- Yang SUDAH difakturkan ke klien.
                    --
                    -- Inilah pembanding biaya yang sebenarnya. Nilai kontrak
                    -- adalah pekerjaan yang akan dikerjakan, bukan yang sudah
                    -- menghasilkan: proyek berbiaya 500 juta dengan kontrak
                    -- 40 miliar akan tampak bermargin 98%, padahal belum
                    -- satu rupiah pun ditagihkan.
                    --
                    -- `dpp` tanpa PPN: PPN dipungut untuk negara, bukan
                    -- pendapatan proyek.
                    SELECT projectName, SUM(dpp) AS tertagih
                    FROM sales_invoices
                    WHERE isDelete = 0
                    GROUP BY projectName
                ) si ON si.projectName = p.code
                WHERE p.isDelete = 0
                ORDER BY p.isActive DESC, p.code ASC
                LIMIT :limit OFFSET :offset
                """,
                {"limit": page_size, "offset": offset},
            )

            data = []
            for x in baris:
                r = dict(x)
                kontrak = float(r["kontrak"] or 0)
                beli = float(r["beli"] or 0)
                internal = float(r["beli_internal"] or 0)
                draft = float(r["draft"] or 0)
                reimburse = float(r["reimburse"] or 0)
                tertagih = float(r["tertagih"] or 0)

                # Draft IKUT dihitung sebagai biaya.
                #
                # Draft belum tentu menjadi pembelian, tetapi biaya yang
                # belum tercatatlah yang paling berbahaya di sini: tanpanya,
                # proyek tampak untung padahal tagihannya belum masuk semua.
                total_biaya = beli + draft + reimburse

                data.append(
                    {
                        "id": r["id"],
                        "code": r["code"],
                        "name": r["name"],
                        "isActive": bool(r["isActive"]),
                        "isCancelled": bool(r["isCancelled"]),
                        "isRetention": bool(r["isRetention"]),
                        "kontrak": kontrak,
                        # Yang SUDAH difakturkan; pembanding biaya yang
                        # sebenarnya. Lihat catatan pada subkuerinya.
                        "tertagih": tertagih,
                        "pembelian": beli,
                        # Bagian pembelian yang berasal dari DALAM grup.
                        #
                        # Sudah termasuk dalam `pembelian`; dikirim tersendiri
                        # agar layar dapat MENGURANGKANNYA bila diminta —
                        # bukan menambahkannya. Sebelumnya layar menghitungnya
                        # dari selisih dua margin, dan itu membuat pembelian
                        # internal masuk dua kali ke dalam biaya.
                        "pembelianInternal": internal,
                        "draft": draft,
                        "reimbursement": reimburse,
                        # Dengan pembelian internal dihitung sebagai biaya.
                        "marginInternalMasuk": kontrak - total_biaya,
                        # Tanpa pembelian internal: yang dibeli dari dalam
                        # perusahaan bukan uang yang keluar dari grup.
                        "marginInternalKeluar": kontrak - (total_biaya - internal),
                    }
                )

            return {
                "data": data,
                "total": total or 0,
                "page": page,
                "page_size": page_size,
                "total_pages": ((total or 0) + page_size - 1) // page_size,
            }
        except Exception as e:
            log_error(f"Error building project margin summary: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def add_contract(project_id: int, data: dict, user_id: int) -> Dict[str, Any]:
        try:
            contract_id = await database.execute(
                insert(project_contracts_table).values(
                    **data,
                    projectID=project_id,
                    createdAt=dt.now(),
                    createdBy=user_id,
                    isDelete=False,
                )
            )
            from repository.audit_log_repository import AuditLogRepository

            # Dicatat pada KONTRAKNYA sendiri.
            #
            # Alasan lama — "kontrak tidak punya halaman sendiri" — sudah
            # tidak berlaku: dialog lihat kontrak kini menampilkan riwayatnya
            # dan mencarinya sebagai `project_contracts` beserta id kontrak
            # itu. Mencatatnya sebagai `projects` membuat riwayat itu selalu
            # kosong, tanpa galat apa pun.
            await AuditLogRepository.record(
                entity="project_contracts",
                # `project_id` dari parameternya, BUKAN `data["projectID"]`.
                #
                # `projectID` tidak pernah ada di dalam `data`: ia disisipkan
                # terpisah pada `insert(...)` di atas. Membacanya dari `data`
                # melempar KeyError — dan karena seluruh fungsi ini dibungkus
                # try/except, galatnya keluar sebagai "Internal server error"
                # SETELAH kontraknya sudah tersimpan.
                entityID=contract_id,
                action="contract_create",
                note=f"{data.get('documentType', 'spk')} {data.get('documentNumber', '')}".strip(),
            )
            return {"message": "Contract added successfully", "contract_id": contract_id}
        except Exception as e:
            log_error(f"Error adding contract: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def get_contract(contract_id: int):
        return await database.fetch_one(
            select(
                project_contracts_table,
                _ekspresi_nilai().label("value"),
            ).where(
                project_contracts_table.c.id == contract_id,
                project_contracts_table.c.isDelete == False,  # noqa: E712
            )
        )

    @staticmethod
    async def update_contract(
        contract_id: int, values: dict, user_id: int
    ) -> Dict[str, Any]:
        try:
            _sebelum = await database.fetch_one(
                select(project_contracts_table).where(
                    project_contracts_table.c.id == contract_id
                )
            )
            if _sebelum is None:
                return {"error": "Contract not found", "status": 404}

            values = {**values, "updatedAt": dt.now(), "updatedBy": user_id}
            await database.execute(
                update(project_contracts_table)
                .where(project_contracts_table.c.id == contract_id)
                .where(project_contracts_table.c.isDelete == False)  # noqa: E712
                .values(**values)
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                # Dicatat pada KONTRAKNYA, bukan pada proyeknya.
                #
                # Layar riwayat kontrak mencari `project_contracts` beserta id
                # kontrak itu sendiri; mencatatnya sebagai `projects` membuat
                # riwayatnya selalu kosong — tanpa galat, hanya daftar hampa
                # yang tampak seperti belum pernah ada perubahan.
                entity="project_contracts",
                entityID=_sebelum["id"],
                action="contract_update",
                changes=AuditLogRepository.diff(dict(_sebelum), values),
                note=f"{_sebelum['documentType']} {_sebelum['documentNumber']}".strip(),
            )
            return {"message": "Contract updated successfully"}
        except Exception as e:
            log_error(f"Error updating contract: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def delete_contract(contract_id: int, user_id: int) -> Dict[str, Any]:
        try:
            # Dibaca lebih dulu: setelah ditandai terhapus, proyek asalnya
            # masih terbaca, tetapi nomor dokumennya perlu direkam pada
            # jejak agar dapat dikenali tanpa membuka baris yang sudah
            # dihapus.
            _sebelum = await ProjectRepository.get_contract(contract_id)
            if _sebelum is None:
                return {"error": "Contract not found", "status": 404}

            await database.execute(
                update(project_contracts_table)
                .where(project_contracts_table.c.id == contract_id)
                .values(isDelete=True, deletedAt=dt.now(), deletedBy=user_id)
            )
            from repository.audit_log_repository import AuditLogRepository

            await AuditLogRepository.record(
                entity="project_contracts",
                entityID=_sebelum["id"],
                action="contract_delete",
                note=(
                    f"{_sebelum['documentType']} {_sebelum['documentNumber']} "
                    f"({_sebelum['dpp']})"
                ).strip(),
            )
            return {"message": "Contract deleted successfully"}
        except Exception as e:
            log_error(f"Error deleting contract: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
