import json

from repository.user_avatar_repository import (
    AVATAR_FIELDS,
    DEFAULT_AVATAR,
    UserAvatarRepository,
)
from utils.redis import r
from utils.logger_utils import log_error

# Redis is a cache only — the database stays the source of truth, so a flushed
# or evicted cache never loses an avatar.
CACHE_PREFIX = "user:avatar:"
CACHE_TTL_SECONDS = 60 * 60 * 24  # 1 day


def _cache_key(user_id: int) -> str:
    return f"{CACHE_PREFIX}{user_id}"


def _to_payload(user_id: int, row: dict | None) -> dict:
    """Normalise a DB row (or a missing one) into the API shape."""
    source = row or DEFAULT_AVATAR
    payload = {field: source.get(field) for field in AVATAR_FIELDS}
    payload["userID"] = user_id
    payload["isDefault"] = row is None
    return payload


class UserAvatarController:
    @staticmethod
    async def get_avatar(user_id: int):
        # 1. cache
        try:
            cached = r.get(_cache_key(user_id))
            if cached:
                return json.loads(cached)
        except Exception as e:
            # a cache failure must never break the request
            log_error(f"Redis read failed for avatar {user_id}: {str(e)}")

        # 2. database
        row = await UserAvatarRepository.get_by_user_id(user_id)
        if isinstance(row, dict) and "error" in row:
            return row

        payload = _to_payload(user_id, row)

        # 3. warm the cache
        try:
            r.setex(_cache_key(user_id), CACHE_TTL_SECONDS, json.dumps(payload))
        except Exception as e:
            log_error(f"Redis write failed for avatar {user_id}: {str(e)}")

        return payload

    @staticmethod
    async def get_avatars(user_ids: list[int]):
        """Batch endpoint for list views: cache hits first, DB for the rest."""
        result: dict[int, dict] = {}
        missing: list[int] = []

        for user_id in user_ids:
            try:
                cached = r.get(_cache_key(user_id))
            except Exception:
                cached = None
            if cached:
                try:
                    result[user_id] = json.loads(cached)
                    continue
                except Exception:
                    pass
            missing.append(user_id)

        if missing:
            rows = await UserAvatarRepository.get_by_user_ids(missing)
            if isinstance(rows, dict) and "error" in rows:
                return rows

            by_user = {row["userID"]: row for row in rows}
            for user_id in missing:
                payload = _to_payload(user_id, by_user.get(user_id))
                result[user_id] = payload
                try:
                    r.setex(
                        _cache_key(user_id),
                        CACHE_TTL_SECONDS,
                        json.dumps(payload),
                    )
                except Exception:
                    pass

        # keep the requested order
        return [result[user_id] for user_id in user_ids if user_id in result]

    @staticmethod
    async def save_avatar(user_id: int, values: dict):
        row = await UserAvatarRepository.upsert(user_id, values)
        if isinstance(row, dict) and "error" in row:
            return row

        payload = _to_payload(user_id, row)

        # refresh the cache immediately so other views see the new avatar
        try:
            r.setex(_cache_key(user_id), CACHE_TTL_SECONDS, json.dumps(payload))
        except Exception as e:
            log_error(f"Redis refresh failed for avatar {user_id}: {str(e)}")

        return payload