from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from utils.auth_utils import get_current_user, User
from utils.webpush import VAPID_PUBLIC_KEY, push_aktif
from repository.push_subscription_repository import PushSubscriptionRepository
from schemas.push_schema import PushSubscribe, PushUnsubscribe

"""
Langganan Web Push.

Berlangganan hanya butuh AKUN, bukan izin modul tertentu: yang dilanggani
adalah pemberitahuan untuk dirinya sendiri, dan siapa yang benar-benar
DIKIRIMI ditentukan saat pengirimannya (mis. hanya pemeriksa saat PO dibuat),
bukan di sini.
"""

router = APIRouter()


@router.get("/vapid-public-key")
async def vapid_public_key():
    """Kunci publik VAPID untuk `applicationServerKey` di peramban."""
    return {"publicKey": VAPID_PUBLIC_KEY, "enabled": push_aktif()}


@router.post("/subscribe")
async def subscribe(
    data: PushSubscribe,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Simpan langganan push milik perangkat pengguna ini."""
    hasil = await PushSubscriptionRepository.simpan(
        user_id=current_user["id"],
        endpoint=data.endpoint,
        p256dh=data.keys.p256dh,
        auth=data.keys.auth,
        user_agent=data.userAgent,
    )
    if "error" in hasil:
        raise HTTPException(status_code=hasil.get("status", 500), detail=hasil["error"])
    return hasil


@router.post("/unsubscribe")
async def unsubscribe(
    data: PushUnsubscribe,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Hapus langganan (saat pengguna mematikan notifikasi)."""
    hasil = await PushSubscriptionRepository.hapus(data.endpoint)
    if "error" in hasil:
        raise HTTPException(status_code=hasil.get("status", 500), detail=hasil["error"])
    return hasil
