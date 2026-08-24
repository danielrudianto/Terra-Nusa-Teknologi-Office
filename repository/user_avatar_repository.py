from datetime import datetime

from sqlalchemy import insert, select, update
from utils.database import database
from models.user_avatar_model import user_avatars_table
from utils.logger_utils import log_error
from utils.errors import internal_error

# Fields that make up an avatar. Kept in one place so the controller, the
# Redis cache and the API response never drift apart.
AVATAR_FIELDS = [
    "faceID",
    "hairID",
    "eyesID",
    "mouthID",
    "topID",
    "accessoryID",
    "skinTone",
    "hairColor",
    "topColor",
    "backgroundColor",
]

DEFAULT_AVATAR = {
    "faceID": "face-01",
    "hairID": "hair-01",
    "eyesID": "eyes-01",
    "mouthID": "mouth-01",
    "topID": "top-01",
    "accessoryID": None,
    "skinTone": "tone-03",
    "hairColor": "hair-brown",
    "topColor": "top-blue",
    "backgroundColor": "bg-blue",
}


class UserAvatarRepository:
    @staticmethod
    async def get_by_user_id(user_id: int):
        try:
            query = select(user_avatars_table).where(
                user_avatars_table.c.userID == user_id
            )
            row = await database.fetch_one(query)
            return dict(row) if row else None
        except Exception as e:
            log_error(f"Error fetching avatar: {str(e)}")
            return internal_error()

    @staticmethod
    async def get_by_user_ids(user_ids: list[int]):
        """Batch fetch — used by list views so we never do N+1 lookups."""
        if not user_ids:
            return []
        try:
            query = select(user_avatars_table).where(
                user_avatars_table.c.userID.in_(user_ids)
            )
            rows = await database.fetch_all(query)
            return [dict(r) for r in rows]
        except Exception as e:
            log_error(f"Error batch fetching avatars: {str(e)}")
            return internal_error()

    @staticmethod
    async def upsert(user_id: int, values: dict):
        """Create the avatar row on first save, update it afterwards."""
        try:
            payload = {k: v for k, v in values.items() if k in AVATAR_FIELDS}

            existing = await UserAvatarRepository.get_by_user_id(user_id)
            if isinstance(existing, dict) and "error" in existing:
                return existing

            if existing is None:
                # `databases` mengeksekusi query yang sudah dikompilasi, jadi
                # default Python-side pada model (default=dt.now) tidak ikut
                # terpasang — waktunya harus diisi eksplisit di sini.
                merged = {
                    **DEFAULT_AVATAR,
                    **payload,
                    "userID": user_id,
                    "createdAt": datetime.now(),
                }
                await database.execute(insert(user_avatars_table).values(**merged))
            else:
                await database.execute(
                    update(user_avatars_table)
                    .where(user_avatars_table.c.userID == user_id)
                    .values(**payload, updatedAt=datetime.now())
                )

            return await UserAvatarRepository.get_by_user_id(user_id)
        except Exception as e:
            log_error(f"Error saving avatar: {str(e)}")
            return internal_error()