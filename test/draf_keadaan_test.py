"""
Draf pembelian punya TIGA keadaan, dan ketiganya berbeda artinya.

Sebelumnya hanya dua: `isDelete` 0 atau 1 — dan yang 1 ditampilkan layar
sebagai "Disetujui" berlencana centang hijau. Draf yang barusan DIHAPUS
karena itu terbaca sebagai pekerjaan yang sudah beres, dan tidak ada yang
tahu bedanya dengan draf yang benar-benar menjadi pembelian.
"""
from unittest.mock import AsyncMock, patch

import pytest

import models.purchase_draft_model as m
from models.purchase_draft_model import PurchaseDraft


async def _kondisi(**saring):
    """Jalankan kuerinya dan kembalikan SQL WHERE-nya sebagai teks."""
    tangkap = {}

    async def fetch_all(q, *a, **k):
        tangkap.setdefault("q", str(q))
        return []

    async def fetch_val(q, *a, **k):
        return 0

    with patch.object(m.database, "fetch_all", AsyncMock(side_effect=fetch_all)), \
         patch.object(m.database, "fetch_one", AsyncMock(return_value={"jumlah": 0})), \
         patch.object(m.database, "fetch_val", AsyncMock(side_effect=fetch_val)):
        await PurchaseDraft.get_purchase_draft(
            1, 10, saring.get("isPending", False), saring.get("isApproved", False),
            "date", "desc", "", saring.get("isConverted", False),
            saring.get("isDeleted", False),
            saring.get("periodFrom"),
            saring.get("periodTo"),
        )
    return tangkap.get("q", "")


@pytest.mark.asyncio
async def test_tertunda_bukan_yang_sudah_dikonversi_atau_dihapus():
    sql = await _kondisi(isPending=True)
    assert '"isDelete" = false' in sql and '"convertedAt" IS NULL' in sql


@pytest.mark.asyncio
async def test_konversi_disaring_dari_convertedat():
    sql = await _kondisi(isConverted=True)
    assert '"convertedAt" IS NOT NULL' in sql


@pytest.mark.asyncio
async def test_dihapus_disaring_dari_isdelete():
    sql = await _kondisi(isDeleted=True)
    assert '"isDelete" = true' in sql
    assert '"convertedAt" IS NOT NULL' not in sql


@pytest.mark.asyncio
async def test_nama_lama_isapproved_tetap_berarti_dihapus():
    """Pemanggil lama tidak boleh patah — dan artinya tidak boleh bergeser."""
    lama = await _kondisi(isApproved=True)
    baru = await _kondisi(isDeleted=True)
    assert lama == baru


@pytest.mark.asyncio
async def test_tanpa_rentang_periode_tidak_ada_penyaring_periode():
    """
    Nama kolomnya selalu muncul di daftar SELECT, jadi yang diperiksa
    `coalesce` — yang hanya dibangun oleh penyaring periode.
    """
    sql = (await _kondisi(isPending=True)).lower()
    assert "coalesce" not in sql


@pytest.mark.asyncio
async def test_rentang_periode_menyaring_yang_bersinggungan():
    """
    Yang dicari draf yang BERSINGGUNGAN dengan rentangnya, bukan yang
    seluruhnya berada di dalamnya: awal <= batas akhir DAN akhir >= batas
    awal. Memakai `periodStart >= from AND periodEnd <= to` membuang
    pekerjaan yang membentang melewati akhir bulan — dan tagihannya kurang.
    """
    sql = await _kondisi(isPending=True, periodFrom="2026-09-01",
                         periodTo="2026-09-30")
    assert "coalesce" in sql.lower()
    assert "<=" in sql and ">=" in sql


@pytest.mark.asyncio
async def test_draf_tanpa_periode_dinilai_dari_tanggal_dokumennya():
    """
    Draf lama tidak berperiode. Bila periodenya dibaca apa adanya, draf itu
    tidak pernah masuk rentang mana pun — hilang dari setiap penyaringan dan
    tidak pernah tertagih. `coalesce` ke kolom `date` yang menahannya.
    """
    sql = (await _kondisi(isPending=True, periodTo="2026-09-30")).lower()
    kutip = sql[sql.index("coalesce"):]
    assert "date" in kutip[:200]
