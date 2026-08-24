"""
Pengujian penyimpanan langganan Web Push.

Ditulis setelah kejadian nyata: menyalakan notifikasi selalu berakhir
`500 Internal Server Error` pada `POST /push/subscribe`, sementara seluruh
tahap sebelumnya — izin, service worker, kunci VAPID, langganan peramban —
sudah benar. Sebabnya satu baris yang tak terlihat:

    `createdAt` diserahkan ke `default=dt.now` milik kolomnya.

Pustaka `databases` menyusun kuerinya sendiri dan TIDAK menjalankan default
Python itu; yang terkirim NULL, kolomnya NOT NULL, dan MySQL menolak dengan
1048. Repository lain di proyek ini selalu mengisi `createdAt` sendiri —
yang ini satu-satunya yang tertinggal, dan tidak ada yang menjaganya.

Yang dijaga di sini:

  * `createdAt` IKUT terkirim dan berisi waktu, bukan NULL;
  * user agent yang kepanjangan dipangkas, bukan menggagalkan seluruh baris;
  * endpoint yang sama tidak menggandakan baris (ON DUPLICATE KEY UPDATE);
  * kegagalan basis data tetap menghasilkan galat yang tertangani, bukan
    lemparan mentah ke pemanggil.
"""

from datetime import datetime

import pytest

from repository import push_subscription_repository as modul
from repository.push_subscription_repository import PushSubscriptionRepository


@pytest.fixture
def kueri(monkeypatch):
    """Tangkap kueri yang dieksekusi; tidak ada MySQL yang dijalankan."""
    catatan = {}

    async def _execute(query):
        # Parameter dibaca lewat jalur kompilasi yang SAMA dengan yang dipakai
        # `databases` — kalau tidak, cacat yang diuji justru tak terlihat.
        from sqlalchemy.dialects import mysql

        compiled = query.compile(dialect=mysql.dialect())
        catatan["params"] = dict(compiled.construct_params())
        catatan["sql"] = str(compiled)
        return 1

    monkeypatch.setattr(modul.database, "execute", _execute)
    return catatan


@pytest.mark.asyncio
async def test_created_at_terisi_bukan_null(kueri):
    """Inti cacatnya: NULL di kolom NOT NULL membuat seluruh simpan gagal."""
    hasil = await PushSubscriptionRepository.simpan(
        user_id=7,
        endpoint="https://wns.windows.com/abc",
        p256dh="kunci-p256dh",
        auth="kunci-auth",
        user_agent="Mozilla/5.0",
    )

    assert hasil == {"message": "Langganan tersimpan"}
    assert kueri["params"]["createdAt"] is not None
    assert isinstance(kueri["params"]["createdAt"], datetime)


@pytest.mark.asyncio
async def test_nilai_langganan_tersimpan_apa_adanya(kueri):
    await PushSubscriptionRepository.simpan(
        user_id=7,
        endpoint="https://fcm.googleapis.com/xyz",
        p256dh="P",
        auth="A",
        user_agent="UA",
    )
    p = kueri["params"]
    assert p["userID"] == 7
    assert p["endpoint"] == "https://fcm.googleapis.com/xyz"
    assert p["p256dh"] == "P"
    assert p["auth"] == "A"
    assert p["userAgent"] == "UA"


@pytest.mark.asyncio
async def test_endpoint_sama_diperbarui_bukan_digandakan(kueri):
    """Memasang ulang di perangkat yang sama tidak menambah baris."""
    await PushSubscriptionRepository.simpan(
        user_id=7, endpoint="e", p256dh="P", auth="A"
    )
    assert "ON DUPLICATE KEY UPDATE" in kueri["sql"].upper()


@pytest.mark.asyncio
async def test_user_agent_panjang_dipangkas(kueri):
    """Keterangan yang kepanjangan tidak boleh menggagalkan langganan sah."""
    await PushSubscriptionRepository.simpan(
        user_id=7,
        endpoint="e",
        p256dh="P",
        auth="A",
        user_agent="X" * 400,
    )
    assert len(kueri["params"]["userAgent"]) == 255


@pytest.mark.asyncio
async def test_user_agent_kosong_boleh(kueri):
    hasil = await PushSubscriptionRepository.simpan(
        user_id=7, endpoint="e", p256dh="P", auth="A", user_agent=None
    )
    assert hasil == {"message": "Langganan tersimpan"}
    assert kueri["params"]["userAgent"] is None


@pytest.mark.asyncio
async def test_galat_basis_data_ditangani(monkeypatch):
    """Kegagalan nyata tetap menjadi galat terkelola, bukan lemparan mentah."""

    async def _meledak(query):
        raise RuntimeError("(1048, \"Column 'createdAt' cannot be null\")")

    monkeypatch.setattr(modul.database, "execute", _meledak)

    hasil = await PushSubscriptionRepository.simpan(
        user_id=7, endpoint="e", p256dh="P", auth="A"
    )
    assert hasil["status"] == 500
    assert "error" in hasil
