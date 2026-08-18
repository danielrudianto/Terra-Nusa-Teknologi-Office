from datetime import date, datetime as dt
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, insert, select, update

from models.bank_model import bank_accounts_table
from models.payment_plan_model import payment_plans_table
from utils.database import database
from utils.logger_utils import log_error


class PaymentPlanRepository:
    @staticmethod
    async def buat(nilai: dict, user_id: int) -> Dict[str, Any]:
        try:
            plan_id = await database.execute(
                insert(payment_plans_table).values(
                    **nilai,
                    status="rencana",
                    createdAt=dt.now(),
                    createdBy=user_id,
                )
            )
            return {"id": plan_id}
        except Exception as e:
            log_error(f"Error creating payment plan: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def ambil(plan_id: int) -> Optional[Dict[str, Any]]:
        try:
            baris = await database.fetch_one(
                select(payment_plans_table).where(
                    payment_plans_table.c.id == plan_id,
                    payment_plans_table.c.isDelete == False,  # noqa: E712
                )
            )
            return dict(baris) if baris else None
        except Exception as e:
            log_error(f"Error fetching payment plan: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def rentang(
        awal: date,
        akhir: date,
        project_name: str = "",
        sertakan_batal: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Rencana dalam satu rentang tanggal.

        Nama rekening ikut diambil supaya kalender tidak perlu satu permintaan
        tambahan per baris.

        Yang BATAL dikecualikan secara bawaan: ia tetap tersimpan sebagai
        riwayat, tetapi memasukkannya ke perhitungan kas membuat angka yang
        ditampilkan lebih besar daripada yang benar-benar akan keluar.
        """
        try:
            syarat = [
                payment_plans_table.c.isDelete == False,  # noqa: E712
                payment_plans_table.c.date >= awal,
                payment_plans_table.c.date <= akhir,
            ]
            if not sertakan_batal:
                syarat.append(payment_plans_table.c.status != "batal")
            if project_name:
                syarat.append(payment_plans_table.c.projectName == project_name)

            rows = await database.fetch_all(
                select(
                    payment_plans_table,
                    bank_accounts_table.c.bankName.label("bankName"),
                )
                .select_from(
                    payment_plans_table.outerjoin(
                        bank_accounts_table,
                        payment_plans_table.c.bankAccountID
                        == bank_accounts_table.c.id,
                    )
                )
                .where(and_(*syarat))
                .order_by(payment_plans_table.c.date.asc())
            )
            # Yang sudah lewat DITANDAI, bukan disembunyikan.
            #
            # Ia tetap perlu terlihat di kalender — supaya yang membukanya
            # tahu ada rencana yang terlewat dan dapat menindaklanjutinya —
            # tetapi berhenti ikut dihitung pada posisi kas.
            hari_ini = date.today()
            hasil = []
            for r in rows:
                d = dict(r)
                d["lewat"] = (
                    d["status"] == "rencana" and d["date"] < hari_ini
                )
                hasil.append(d)
            return hasil
        except Exception as e:
            log_error(f"Error listing payment plans: {str(e)}")
            return []

    @staticmethod
    async def ringkasan(awal: date, akhir: date) -> Dict[str, Any]:
        """
        Jumlah rencana per arah dan kategori dalam satu rentang.

        Yang SUDAH LEWAT tanggalnya TIDAK dihitung.

        Rencana yang tanggalnya terlewat tanpa pernah ditandai terpakai
        praktis tidak terjadi — dan membiarkannya ikut membuat posisi kas
        menunjukkan uang yang tidak akan bergerak ke mana pun. Angkanya
        tampak meyakinkan justru karena tidak ada yang salah terlihat.

        Barisnya TIDAK dihapus. Selisih antara yang direncanakan dan yang
        terjadi justru yang menjelaskan mengapa kasnya meleset, dan itu
        hilang bila barisnya lenyap. Ia hanya berhenti dihitung.
        """
        try:
            hari_ini = date.today()
            # Batas bawah: yang lebih akhir antara awal rentang dan hari ini.
            batas = awal if awal > hari_ini else hari_ini

            rows = await database.fetch_all(
                select(
                    payment_plans_table.c.planType,
                    payment_plans_table.c.category,
                    func.sum(payment_plans_table.c.amount).label("total"),
                    func.count().label("jumlah"),
                )
                .where(
                    payment_plans_table.c.isDelete == False,  # noqa: E712
                    payment_plans_table.c.status == "rencana",
                    payment_plans_table.c.date >= batas,
                    payment_plans_table.c.date <= akhir,
                )
                .group_by(
                    payment_plans_table.c.planType,
                    payment_plans_table.c.category,
                )
            )
            data = [dict(r) for r in rows]

            keluar = sum(
                float(x["total"] or 0) for x in data if x["planType"] == "keluar"
            )
            masuk = sum(
                float(x["total"] or 0) for x in data if x["planType"] == "masuk"
            )
            return {
                "perKategori": data,
                "keluar": keluar,
                "masuk": masuk,
                # Yang dilihat orang adalah selisihnya, bukan salah satunya.
                "selisih": masuk - keluar,
                # Disebut supaya layar dapat menjelaskan mengapa angkanya
                # berbeda dari jumlah baris yang terlihat di kalender.
                "dihitungSejak": batas.isoformat(),
            }
        except Exception as e:
            log_error(f"Error summarising payment plans: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def ubah(plan_id: int, nilai: dict, user_id: int) -> Dict[str, Any]:
        try:
            await database.execute(
                update(payment_plans_table)
                .where(payment_plans_table.c.id == plan_id)
                .values(**nilai, updatedAt=dt.now(), updatedBy=user_id)
            )
            return {"id": plan_id}
        except Exception as e:
            log_error(f"Error updating payment plan: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def hapus(plan_id: int, user_id: int) -> Dict[str, Any]:
        """
        Hapus lunak.

        Rencana yang dihapus tetap tersimpan: yang meninjau posisi kas bulan
        lalu perlu tahu apa yang DIRENCANAKAN, bukan hanya apa yang terjadi —
        selisih keduanya justru yang menjelaskan mengapa kasnya meleset.
        """
        try:
            await database.execute(
                update(payment_plans_table)
                .where(payment_plans_table.c.id == plan_id)
                .values(isDelete=True, deletedAt=dt.now(), deletedBy=user_id)
            )
            return {"id": plan_id}
        except Exception as e:
            log_error(f"Error deleting payment plan: {str(e)}")
            return {"error": "Internal server error.", "status": 500}
