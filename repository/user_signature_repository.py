from datetime import datetime as dt

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert

from models.user_signature_model import user_signatures_table
from utils.database import database
from utils.errors import internal_error
from utils.logger_utils import log_error


class UserSignatureRepository:
    """Baca & simpan tanda tangan pengguna."""

    @staticmethod
    async def punya(user_id: int) -> bool:
        """
        Sudah punya tanda tangan?

        Dipisah dari `ambil()` dan TIDAK membaca kolom gambarnya. Layar
        menanyakan ini pada setiap login; menjawabnya dengan menarik blob
        berarti mengirimkan puluhan kilobita hanya untuk menghasilkan satu
        kata "sudah".
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
        mime: str = "image/png",
    ):
        """
        Simpan atau ganti tanda tangan seseorang.

        SATU perintah, bukan "periksa dulu lalu sisip/ubah". Dua permintaan
        yang datang bersamaan dari dua perangkat sama-sama melihat "belum
        ada", lalu keduanya menyisip — dan kunci unik pada `userID` membuat
        yang kedua gagal dengan galat basis data mentah di layar orang.
        `ON DUPLICATE KEY UPDATE` menyelesaikannya di satu langkah.
        """
        try:
            nilai = {
                "userID": user_id,
                "image": gambar,
                "mimeType": mime,
                "width": lebar,
                "height": tinggi,
                "createdAt": dt.now(),
            }
            perintah = mysql_insert(user_signatures_table).values(**nilai)
            perintah = perintah.on_duplicate_key_update(
                image=perintah.inserted.image,
                mimeType=perintah.inserted.mimeType,
                width=perintah.inserted.width,
                height=perintah.inserted.height,
                updatedAt=dt.now(),
            )
            await database.execute(perintah)
            return {"ok": True}
        except Exception as e:
            log_error(f"Error saving signature: {str(e)}")
            return internal_error()
