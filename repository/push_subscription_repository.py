from datetime import datetime as dt
from typing import Any, Dict, List

from sqlalchemy import select, insert, delete
from sqlalchemy.dialects.mysql import insert as mysql_insert

from utils.database import database
from utils.logger_utils import log_error
from models.push_subscription_model import push_subscriptions_table
from models.user_model import users_table
from models.user_department_model import user_departments_table


class PushSubscriptionRepository:
    """Simpan & ambil langganan Web Push."""

    @staticmethod
    async def simpan(
        user_id: int,
        endpoint: str,
        p256dh: str,
        auth: str,
        user_agent: str | None = None,
    ) -> Dict[str, Any]:
        """
        Simpan langganan. Endpoint yang sama diperbarui, bukan digandakan —
        memasang ulang di perangkat yang sama tidak menambah baris baru, dan
        bila pindah akun, kepemilikannya ikut berpindah.
        """
        # User agent DIPANGKAS ke muat kolomnya.
        #
        # Kolomnya VARCHAR(255) dan isinya sekadar keterangan perangkat pada
        # daftar. Peramban tertentu mengirim untai yang lebih panjang, dan
        # MySQL bermodus ketat menolak seluruh barisnya — langganan yang sah
        # gagal tersimpan hanya karena keterangannya kepanjangan.
        if user_agent and len(user_agent) > 255:
            user_agent = user_agent[:255]

        try:
            # `createdAt` DIISI DI SINI, bukan diserahkan ke default kolom.
            #
            # Pustaka `databases` menyusun kueri lewat jalurnya sendiri:
            # kolom yang default-nya berupa fungsi Python tidak pernah
            # dijalankan, dan yang terkirim ke MySQL adalah NULL. Karena
            # kolomnya NOT NULL, setiap penyimpanan langganan gagal dengan
            # galat 1048 — dan yang menekan tombol hanya melihat 500.
            #
            # Seluruh repository lain di proyek ini memang sudah mengisinya
            # sendiri (lihat audit_log & user_avatar); yang ini satu-satunya
            # yang tertinggal.
            sisip = mysql_insert(push_subscriptions_table).values(
                userID=user_id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
                userAgent=user_agent,
                createdAt=dt.now(),
            )
            upsert = sisip.on_duplicate_key_update(
                userID=user_id,
                p256dh=p256dh,
                auth=auth,
                userAgent=user_agent,
            )
            await database.execute(upsert)
            return {"message": "Langganan tersimpan"}
        except Exception as e:
            log_error(f"Gagal menyimpan langganan push: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def hapus(endpoint: str) -> Dict[str, Any]:
        """Hapus satu langganan berdasarkan endpoint-nya."""
        try:
            await database.execute(
                delete(push_subscriptions_table).where(
                    push_subscriptions_table.c.endpoint == endpoint
                )
            )
            return {"message": "Langganan dihapus"}
        except Exception as e:
            log_error(f"Gagal menghapus langganan push: {str(e)}")
            return {"error": "Internal server error.", "status": 500}

    @staticmethod
    async def hapus_mati(endpoint: str) -> None:
        """Buang langganan yang ditolak layanan push (404/410)."""
        try:
            await database.execute(
                delete(push_subscriptions_table).where(
                    push_subscriptions_table.c.endpoint == endpoint
                )
            )
        except Exception as e:
            log_error(f"Gagal membuang langganan mati: {str(e)}")

    @staticmethod
    async def untuk_pengguna(user_ids: List[int]) -> List[Dict[str, Any]]:
        """Seluruh langganan milik daftar pengguna ini."""
        if not user_ids:
            return []
        try:
            rows = await database.fetch_all(
                select(push_subscriptions_table).where(
                    push_subscriptions_table.c.userID.in_(user_ids)
                )
            )
            return [dict(r) for r in rows]
        except Exception as e:
            log_error(f"Gagal mengambil langganan push: {str(e)}")
            return []

    @staticmethod
    async def pemeriksa_ids(kecuali_user_id: int | None = None) -> List[int]:
        """
        Pengguna yang BOLEH memeriksa purchase order — cerminan
        `boleh_memeriksa` di server: level 4 ke atas, atau level 3 yang berada
        di divisi procurement. Pembuatnya dikecualikan (opsional): tak ada
        gunanya memberi tahu orang untuk memeriksa dokumennya sendiri, yang
        memang ditolak server.
        """
        try:
            rows = await database.fetch_all(
                select(
                    users_table.c.id,
                    users_table.c.authenticationLevel,
                ).where(users_table.c.isDeleted == False)  # noqa: E712
            )
            # Divisi diambil sekali untuk semua, lalu dipadankan di memori.
            dept_rows = await database.fetch_all(select(user_departments_table))
            divisi: dict[int, set[str]] = {}
            for d in dept_rows:
                divisi.setdefault(d["userID"], set()).add(d["department"])

            hasil: List[int] = []
            for r in rows:
                uid = r["id"]
                lv = int(r["authenticationLevel"] or 1)
                boleh = lv >= 4 or (lv == 3 and "procurement" in divisi.get(uid, set()))
                if boleh and uid != kecuali_user_id:
                    hasil.append(uid)
            return hasil
        except Exception as e:
            log_error(f"Gagal menentukan pemeriksa: {str(e)}")
            return []

    @staticmethod
    async def penyetuju_ids(
        kecuali_user_ids: List[int] | None = None,
    ) -> List[int]:
        """
        Pengguna yang BOLEH menyetujui purchase order: level 4 ke atas.

        Cerminan aturan persetujuan di `update_status` — dokumen yang sudah
        diperiksa menunggu keputusan level 4/5. Beberapa pengguna dapat
        dikecualikan sekaligus: minimal pemeriksanya sendiri (server memang
        menolak pemeriksa menyetujui periksaannya) dan pembuatnya (ia diberi
        kabar tersendiri, bukan diminta menyetujui).
        """
        try:
            rows = await database.fetch_all(
                select(
                    users_table.c.id,
                    users_table.c.authenticationLevel,
                ).where(users_table.c.isDeleted == False)  # noqa: E712
            )
            kecuali = {int(u) for u in (kecuali_user_ids or []) if u is not None}
            return [
                r["id"]
                for r in rows
                if int(r["authenticationLevel"] or 1) >= 4
                and r["id"] not in kecuali
            ]
        except Exception as e:
            log_error(f"Gagal menentukan penyetuju: {str(e)}")
            return []
