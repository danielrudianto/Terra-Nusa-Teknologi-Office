from datetime import datetime as dt

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert

from models.user_model import users_table
from models.user_signature_model import (
    user_signature_requests_table,
    user_signatures_table,
)
from utils.database import database
from utils.errors import internal_error
from utils.logger_utils import log_error


class UserSignatureRepository:
    """Baca & simpan tanda tangan pengguna beserta permintaan penggantiannya."""

    # ------------------------------------------------------------------
    # Tanda tangan yang BERLAKU
    # ------------------------------------------------------------------

    @staticmethod
    async def punya(user_id: int) -> bool:
        """
        Sudah punya tanda tangan?

        TIDAK membaca kolom gambarnya. Layar menanyakan ini pada setiap login;
        menjawabnya dengan menarik blob berarti mengirim puluhan kilobita
        hanya untuk menghasilkan satu kata "sudah".
        """
        try:
            ada = await database.fetch_val(
                select(user_signatures_table.c.id).where(
                    user_signatures_table.c.userID == user_id
                )
            )
            return ada is not None
        except Exception as e:
            log_error(f"Error checking signature: {str(e)}")
            return False

    @staticmethod
    async def ambil(user_id: int):
        """Baris tanda tangan milik seseorang, atau None."""
        try:
            row = await database.fetch_one(
                select(user_signatures_table).where(
                    user_signatures_table.c.userID == user_id
                )
            )
            return dict(row) if row else None
        except Exception as e:
            log_error(f"Error fetching signature: {str(e)}")
            return internal_error()

    @staticmethod
    async def simpan(
        user_id: int,
        gambar: bytes,
        lebar: int | None,
        tinggi: int | None,
        sidik: str | None = None,
        disetujui_oleh: int | None = None,
        mime: str = "image/png",
    ):
        """
        Simpan atau ganti tanda tangan yang BERLAKU.

        SATU perintah, bukan "periksa dulu lalu sisip/ubah". Dua permintaan
        yang datang bersamaan dari dua perangkat sama-sama melihat "belum
        ada", lalu keduanya menyisip — dan kunci unik pada `userID` membuat
        yang kedua gagal dengan galat basis data mentah di layar orang.
        """
        try:
            nilai = {
                "userID": user_id,
                "image": gambar,
                "mimeType": mime,
                "width": lebar,
                "height": tinggi,
                "fingerprint": sidik,
                "approvedBy": disetujui_oleh,
                "approvedAt": dt.now() if disetujui_oleh else None,
                "createdAt": dt.now(),
            }
            perintah = mysql_insert(user_signatures_table).values(**nilai)
            perintah = perintah.on_duplicate_key_update(
                image=perintah.inserted.image,
                mimeType=perintah.inserted.mimeType,
                width=perintah.inserted.width,
                height=perintah.inserted.height,
                fingerprint=perintah.inserted.fingerprint,
                approvedBy=perintah.inserted.approvedBy,
                approvedAt=perintah.inserted.approvedAt,
                updatedAt=dt.now(),
            )
            await database.execute(perintah)
            return {"ok": True}
        except Exception as e:
            log_error(f"Error saving signature: {str(e)}")
            return internal_error()

    # ------------------------------------------------------------------
    # Bahan pembanding kemiripan
    # ------------------------------------------------------------------

    @staticmethod
    async def sidik_orang_lain(user_id: int):
        """
        Sidik milik SEMUA pengguna lain — yang berlaku maupun yang tertunda.

        Yang tertunda ikut dibandingkan, dan itu perlu: dua akun yang
        mengajukan gambar yang sama pada hari yang sama tidak akan saling
        tertangkap bila hanya yang sudah berlaku yang dibandingkan.

        Kolom GAMBARNYA tidak ikut terbaca — yang dibandingkan sidiknya, dan
        menarik puluhan blob untuk itu sia-sia.
        """
        try:
            aktif = await database.fetch_all(
                select(
                    user_signatures_table.c.userID,
                    user_signatures_table.c.fingerprint,
                    users_table.c.name,
                )
                .select_from(
                    user_signatures_table.join(
                        users_table, users_table.c.id == user_signatures_table.c.userID
                    )
                )
                .where(
                    user_signatures_table.c.userID != user_id,
                    user_signatures_table.c.fingerprint.isnot(None),
                )
            )
            tertunda = await database.fetch_all(
                select(
                    user_signature_requests_table.c.userID,
                    user_signature_requests_table.c.fingerprint,
                    users_table.c.name,
                )
                .select_from(
                    user_signature_requests_table.join(
                        users_table,
                        users_table.c.id == user_signature_requests_table.c.userID,
                    )
                )
                .where(
                    user_signature_requests_table.c.userID != user_id,
                    user_signature_requests_table.c.status == "pending",
                    user_signature_requests_table.c.fingerprint.isnot(None),
                )
            )
            return [dict(r) for r in list(aktif) + list(tertunda)]
        except Exception as e:
            log_error(f"Error fetching fingerprints: {str(e)}")
            return []

    # ------------------------------------------------------------------
    # Permintaan penggantian
    # ------------------------------------------------------------------

    @staticmethod
    async def tertunda_milik(user_id: int):
        """Permintaan yang masih menunggu keputusan, milik satu orang."""
        try:
            row = await database.fetch_one(
                select(
                    user_signature_requests_table.c.id,
                    user_signature_requests_table.c.createdAt,
                    user_signature_requests_table.c.similarity,
                    user_signature_requests_table.c.similarTo,
                ).where(
                    user_signature_requests_table.c.userID == user_id,
                    user_signature_requests_table.c.status == "pending",
                )
            )
            return dict(row) if row else None
        except Exception as e:
            log_error(f"Error fetching pending signature: {str(e)}")
            return None

    @staticmethod
    async def batalkan_tertunda(user_id: int):
        """
        Tutup permintaan lama yang masih menunggu.

        Mengajukan dua kali berarti yang kedua yang dimaksud. Tanpa ini,
        antreannya berisi dua permintaan dari orang yang sama dan penyetuju
        harus menebak mana yang terakhir.
        """
        try:
            await database.execute(
                update(user_signature_requests_table)
                .where(
                    user_signature_requests_table.c.userID == user_id,
                    user_signature_requests_table.c.status == "pending",
                )
                .values(
                    status="rejected",
                    decidedAt=dt.now(),
                    decisionNote="diganti permintaan yang lebih baru",
                )
            )
        except Exception as e:
            log_error(f"Error closing pending signature: {str(e)}")

    @staticmethod
    async def buat_permintaan(
        user_id: int,
        gambar: bytes,
        lebar: int | None,
        tinggi: int | None,
        sidik: str | None,
        kemiripan: float | None,
        mirip_dengan: int | None,
        status: str = "pending",
        disetujui_oleh: int | None = None,
        catatan: str | None = None,
    ):
        """Catat satu versi tanda tangan — tertunda, atau langsung berlaku."""
        try:
            nilai = {
                "userID": user_id,
                "image": gambar,
                "mimeType": "image/png",
                "width": lebar,
                "height": tinggi,
                "fingerprint": sidik,
                "status": status,
                "similarity": kemiripan,
                "similarTo": mirip_dengan,
                "note": catatan,
                "createdAt": dt.now(),
            }
            if status != "pending":
                nilai["decidedBy"] = disetujui_oleh
                nilai["decidedAt"] = dt.now()
            hasil = await database.execute(
                insert(user_signature_requests_table).values(**nilai)
            )
            return {"id": hasil}
        except Exception as e:
            log_error(f"Error creating signature request: {str(e)}")
            return internal_error()

    @staticmethod
    async def daftar_tertunda():
        """Antrean permintaan beserta gambarnya — hanya untuk penyetuju."""
        try:
            baris = await database.fetch_all(
                select(
                    user_signature_requests_table,
                    users_table.c.name.label("userName"),
                )
                .select_from(
                    user_signature_requests_table.join(
                        users_table,
                        users_table.c.id == user_signature_requests_table.c.userID,
                    )
                )
                .where(user_signature_requests_table.c.status == "pending")
                .order_by(user_signature_requests_table.c.createdAt.asc())
            )
            return [dict(r) for r in baris]
        except Exception as e:
            log_error(f"Error listing signature requests: {str(e)}")
            return internal_error()

    @staticmethod
    async def permintaan(request_id: int):
        try:
            row = await database.fetch_one(
                select(user_signature_requests_table).where(
                    user_signature_requests_table.c.id == request_id
                )
            )
            return dict(row) if row else None
        except Exception as e:
            log_error(f"Error fetching signature request: {str(e)}")
            return internal_error()

    @staticmethod
    async def putuskan(
        request_id: int, status: str, oleh: int, catatan: str | None = None
    ):
        """
        Tandai permintaan sebagai disetujui/ditolak.

        Syaratnya `status = 'pending'` ikut di WHERE, bukan diperiksa lebih
        dulu lalu ditulis: dua penyetuju yang membuka antrean yang sama akan
        sama-sama melihat "masih menunggu", dan tanpa syarat itu keduanya
        menulis — permintaan yang sama tercatat disetujui oleh satu orang dan
        ditolak oleh yang lain.
        """
        try:
            hasil = await database.execute(
                update(user_signature_requests_table)
                .where(
                    user_signature_requests_table.c.id == request_id,
                    user_signature_requests_table.c.status == "pending",
                )
                .values(
                    status=status,
                    decidedBy=oleh,
                    decidedAt=dt.now(),
                    decisionNote=catatan,
                )
            )
            return hasil
        except Exception as e:
            log_error(f"Error deciding signature request: {str(e)}")
            return internal_error()

    @staticmethod
    async def riwayat(user_id: int):
        """Seluruh versi yang pernah diajukan seseorang — tanpa gambarnya."""
        try:
            baris = await database.fetch_all(
                select(
                    user_signature_requests_table.c.id,
                    user_signature_requests_table.c.status,
                    user_signature_requests_table.c.similarity,
                    user_signature_requests_table.c.createdAt,
                    user_signature_requests_table.c.decidedAt,
                    user_signature_requests_table.c.decidedBy,
                    user_signature_requests_table.c.decisionNote,
                )
                .where(user_signature_requests_table.c.userID == user_id)
                .order_by(user_signature_requests_table.c.createdAt.desc())
            )
            return [dict(r) for r in baris]
        except Exception as e:
            log_error(f"Error fetching signature history: {str(e)}")
            return internal_error()

    # ------------------------------------------------------------------
    # Pembubuhan pada dokumen
    # ------------------------------------------------------------------

    @staticmethod
    async def gambar_untuk(user_ids) -> dict:
        """
        Gambar tanda tangan beberapa orang sekaligus, sebagai data-URI.

        DIPAKAI PENCETAK DOKUMEN, bukan layar. Yang meminta di sini server
        sendiri — saat merender CoP/BAP — sehingga gambarnya tidak pernah
        singgah di peramban siapa pun sebelum menjadi bagian dari dokumennya.

        Satu kueri untuk semua id, bukan satu per orang: lembar BAP memuat
        dua penandatangan, dan dua perjalanan ke basis data untuk satu
        cetakan adalah dua kali lipat yang tidak perlu.
        """
        import base64

        bersih = sorted({int(i) for i in (user_ids or []) if i})
        if not bersih:
            return {}
        try:
            baris = await database.fetch_all(
                select(
                    user_signatures_table.c.userID,
                    user_signatures_table.c.image,
                ).where(user_signatures_table.c.userID.in_(bersih))
            )
            return {
                r["userID"]: "data:image/png;base64,"
                + base64.b64encode(r["image"]).decode("ascii")
                for r in baris
            }
        except Exception as e:
            log_error(f"Error fetching signatures for stamping: {str(e)}")
            # Dokumen TETAP tercetak, tanpa tanda tangan. Menggagalkan
            # cetakan karena gambarnya tidak terbaca berarti satu kolom
            # kosong menahan seluruh lembar.
            return {}
