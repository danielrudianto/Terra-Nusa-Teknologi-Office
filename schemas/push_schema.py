from pydantic import BaseModel, Field


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscribe(BaseModel):
    """Langganan yang dikirim peramban lewat PushManager.subscribe()."""

    endpoint: str = Field(..., min_length=1)
    keys: PushKeys
    userAgent: str | None = None


class PushUnsubscribe(BaseModel):
    endpoint: str = Field(..., min_length=1)
