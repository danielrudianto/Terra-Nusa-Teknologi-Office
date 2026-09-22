"""
Pembayaran tertunda & terjadwal untuk saldo rencana: yang BELUM disetujui
sebelum titik mulai dibawa; yang ditolak (isDelete) dan yang sudah disetujui
tidak (sudah ada di view mutation). Dijalankan terhadap basis data uji.
"""

from datetime import date

import pytest

from _integrasi import butuh_db, sambungan  # noqa: F401

# Pola `_integrasi`: berjalan hanya bila TEST_DATABASE_URL disetel, dan
# sambungannya dibuka-tutup di dalam loop uji ini — sambungan global yang
# dibiarkan menempel membuat uji sesudahnya gagal "different loop".
pytestmark = butuh_db


async def test_bawaan_dan_harian(sambungan):
    from repository.kalender_terjadwal_repository import (
        KalenderTerjadwalRepository as R,
    )

    db = sambungan
    try:
        # Kolom yang dipakai repositori ikut diperiksa: basis data uji lama
        # punya `payment_outgoing` berbentuk usang tanpa kolom rekening.
        await db.fetch_one(
            "SELECT bankAccountID, isApprove, isDelete FROM payment_outgoing LIMIT 1"
        )
        await db.fetch_one(
            "SELECT bankAccountID, isApprove, isDelete FROM payment_incoming LIMIT 1"
        )
    except Exception:
        pytest.skip("skema payment_outgoing/incoming basis data uji tidak lengkap")
    akun = 987654
    await db.execute("DELETE FROM payment_outgoing WHERE bankAccountID = :a", {"a": akun})
    await db.execute("SET FOREIGN_KEY_CHECKS = 0")
    try:
        for tgl, jml, setuju, hapus in [
            ("2026-09-24", 100, 0, 0),   # tertunda sebelum Okt  -> dibawa
            ("2026-09-25", 50, 1, 0),    # disetujui             -> sudah di mutation
            ("2026-09-26", 70, 0, 1),    # ditolak               -> tidak
            ("2026-10-03", 30, 0, 0),    # di dalam rentang      -> harian
        ]:
            await db.execute(
                "INSERT INTO payment_outgoing (date, amount, bankAccountID, isApprove, isDelete, createdAt, createdBy, status) "
                "VALUES (:t, :j, :a, :s, :h, NOW(), 1, :st)",
                {"t": tgl, "j": jml, "a": akun, "s": setuju, "h": hapus, "st": "draft"},
            )
        b = await R.bawaan(date(2026, 10, 1), [akun])
        assert len(b) == 1 and b[0]["keluar"] == 100 and b[0]["jumlah"] == 1
        h = await R.harian(date(2026, 10, 1), date(2026, 10, 31), [akun])
        assert h == [{"tanggal": "2026-10-03", "keluar": 30.0, "masuk": 0.0}]
    finally:
        await db.execute("DELETE FROM payment_outgoing WHERE bankAccountID = :a", {"a": akun})
        await db.execute("SET FOREIGN_KEY_CHECKS = 1")
