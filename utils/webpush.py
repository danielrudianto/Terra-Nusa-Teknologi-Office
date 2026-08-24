"""
Pengirim Web Push.

Membungkus `pywebpush` supaya sisa aplikasi cukup memanggil `kirim_ke_pengguna`
tanpa mengurus enkripsi muatan (RFC 8291) maupun VAPID (RFC 8292).

DUA SIFAT PENTING

1. TIDAK MEMBLOKIR. `pywebpush` sinkron (memakai `requests`); dijalankan di
   thread terpisah lewat `asyncio.to_thread` agar tidak menahan event loop.
2. TIDAK PERNAH MENGGAGALKAN PEMANGGILNYA. Memberi tahu adalah efek samping;
   kegagalannya tidak boleh membatalkan pembuatan purchase order. Semua galat
   ditangkap dan dicatat, bukan dilempar.

Langganan yang MATI (peramban mencabut izin) dijawab 404/410 oleh layanan
push; baris itu dihapus saat itu juga supaya daftarnya tidak menumpuk sampah.
"""

from __future__ import annotations

import os
import json
import asyncio
from typing import Any, Dict, List

from utils.logger_utils import log_error, log_info

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
# 'sub' pada klaim VAPID — wajib mailto: atau URL milik pengirim.
VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:admin@alphakonstruksi.id")


def push_aktif() -> bool:
    """Push hanya jalan bila kuncinya terpasang; kalau tidak, diam-diam mati."""
    return bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)


def _kirim_satu(langganan: Dict[str, Any], muatan: str) -> int | None:
    """
    Kirim ke SATU langganan. Kembalian:
      - None  : berhasil (atau diperlakukan berhasil)
      - kode  : status HTTP bila langganannya ditolak (404/410 => mati)
    Dijalankan di thread; jangan panggil langsung dari kode async.
    """
    from pywebpush import webpush, WebPushException

    info = {
        "endpoint": langganan["endpoint"],
        "keys": {"p256dh": langganan["p256dh"], "auth": langganan["auth"]},
    }
    try:
        webpush(
            subscription_info=info,
            data=muatan,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},
            ttl=3600,
        )
        return None
    except WebPushException as e:
        kode = getattr(getattr(e, "response", None), "status_code", None)
        if kode in (404, 410):
            return kode  # langganan mati — akan dibuang pemanggilnya
        log_error(f"Web push gagal ({kode}): {str(e)}")
        return kode or 0
    except Exception as e:
        log_error(f"Web push galat tak terduga: {str(e)}")
        return 0


async def kirim_ke_pengguna(
    user_ids: List[int],
    judul: str,
    pesan: str,
    url: str = "/",
    tag: str | None = None,
    data_tambahan: Dict[str, Any] | None = None,
) -> None:
    """
    Kirim satu notifikasi ke seluruh perangkat milik daftar pengguna.

    Aman dipanggil tanpa `await` menahan alur utama bila dibungkus
    `asyncio.create_task`; di sini tetap async agar pemanggil dapat memilih.
    """
    if not push_aktif():
        return
    if not user_ids:
        return

    # Impor di sini agar modul ini tetap dapat dimuat walau tabel/langganan
    # belum ada saat rutinitas lain mengimpornya.
    from repository.push_subscription_repository import PushSubscriptionRepository

    langganan = await PushSubscriptionRepository.untuk_pengguna(user_ids)
    if not langganan:
        return

    muatan = json.dumps(
        {
            "title": judul,
            "body": pesan,
            "url": url,
            "tag": tag,
            **(data_tambahan or {}),
        }
    )

    dikirim = 0
    for lg in langganan:
        kode = await asyncio.to_thread(_kirim_satu, lg, muatan)
        if kode in (404, 410):
            await PushSubscriptionRepository.hapus_mati(lg["endpoint"])
        elif kode is None:
            dikirim += 1

    if dikirim:
        log_info(f"Web push terkirim ke {dikirim} perangkat: {judul}")
