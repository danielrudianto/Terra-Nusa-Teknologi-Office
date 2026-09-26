"""
Draf pembelian dapat diubah nominal/periodenya — DENGAN jejak nilai lamanya.

Logistik lapangan memasukkan draf setiap hari dan kerap perlu membetulkan
angkanya. Sebelum ini satu-satunya jalan adalah menghapus lalu membuat ulang,
yang menghilangkan siapa yang memasukkannya dan kapan.

Yang dijaga: draf yang sudah menjadi pembelian tidak dapat diubah, hanya
bidang yang benar-benar berubah yang masuk riwayat, dan identitas dokumen
(pemasok, proyek, SPK) tidak ikut dapat diganti.
"""
from unittest.mock import AsyncMock, patch

import pytest

from controllers.purchase_draft_controller import PurchaseDraftController as Ctl
from models.purchase_draft_model import PurchaseDraft


class RekamSepertiRow:
    """
    Tiruan hasil `database.fetch_one` — BUKAN dict.

    `databases` memakai `sqlalchemy.engine.Row`, yang tidak punya `.get()`
    dan yang `in`-nya memeriksa NILAI, bukan nama kolom. Menguji dengan
    dict membuat `draf.get("convertedAt")` tampak jalan padahal di
    produksi ia melempar AttributeError.
    """

    def __init__(self, isi: dict):
        self._isi = dict(isi)

    def keys(self):
        return self._isi.keys()

    def __getitem__(self, kunci):
        return self._isi[kunci]

    def __iter__(self):
        return iter(self._isi.values())

    def __len__(self):
        return len(self._isi)


DRAF = {
    "id": 7, "dpp": 1000000, "ppn": 0, "pbbkb": 0,
    "description": "Solar", "supplierID": 42, "projectName": "R501",
    "convertedAt": None, "isDelete": 0, "periodStart": None, "periodEnd": None,
}


def _draf(**ganti):
    return RekamSepertiRow({**DRAF, **ganti})


@pytest.mark.asyncio
async def test_yang_sudah_dikonversi_tidak_dapat_diubah():
    with patch.object(PurchaseDraft, "get_purchase_draft_by_id",
                      AsyncMock(return_value=_draf(convertedAt="2026-09-01"))), \
         patch.object(PurchaseDraft, "ubah", AsyncMock()) as tulis:
        hasil = await Ctl.ubah_purchase_draft(7, {"dpp": 2000000}, 1)
    assert hasil["status"] == 409 and not tulis.called


@pytest.mark.asyncio
async def test_yang_sudah_dihapus_tidak_dapat_diubah():
    with patch.object(PurchaseDraft, "get_purchase_draft_by_id",
                      AsyncMock(return_value=_draf(isDelete=1))), \
         patch.object(PurchaseDraft, "ubah", AsyncMock()) as tulis:
        hasil = await Ctl.ubah_purchase_draft(7, {"dpp": 2000000}, 1)
    assert hasil["status"] == 409 and not tulis.called


@pytest.mark.asyncio
async def test_identitas_dokumen_tidak_ikut_berubah():
    """Mengganti pemasok berarti ini draf yang lain, bukan draf yang dibetulkan."""
    with patch.object(PurchaseDraft, "get_purchase_draft_by_id",
                      AsyncMock(return_value=_draf())), \
         patch.object(PurchaseDraft, "ubah", AsyncMock(return_value=1)) as tulis, \
         patch("repository.audit_log_repository.AuditLogRepository.record", AsyncMock()):
        await Ctl.ubah_purchase_draft(
            7, {"dpp": 2000000, "supplierID": 99, "projectName": "LAIN"}, 1
        )
    ditulis = tulis.await_args.args[1]
    assert "supplierID" not in ditulis and "projectName" not in ditulis
    assert ditulis == {"dpp": 2000000}


@pytest.mark.asyncio
async def test_riwayat_memuat_nilai_lama_dan_baru():
    catat = AsyncMock()
    with patch.object(PurchaseDraft, "get_purchase_draft_by_id",
                      AsyncMock(return_value=_draf())), \
         patch.object(PurchaseDraft, "ubah", AsyncMock(return_value=1)), \
         patch("repository.audit_log_repository.AuditLogRepository.record", catat):
        hasil = await Ctl.ubah_purchase_draft(7, {"dpp": 2500000}, 9)
    # `from`/`to` — kunci yang dibaca komponen riwayat di seluruh aplikasi.
    # Dengan `dari`/`ke`, barisnya tampil sebagai "— → —".
    assert hasil["perubahan"]["dpp"] == {"from": 1000000, "to": 2500000}
    assert catat.await_args.kwargs["action"] == "update"
    assert catat.await_args.kwargs["changes"]["dpp"]["to"] == 2500000


@pytest.mark.asyncio
async def test_bidang_yang_tidak_berubah_tidak_masuk_riwayat():
    catat = AsyncMock()
    with patch.object(PurchaseDraft, "get_purchase_draft_by_id",
                      AsyncMock(return_value=_draf())), \
         patch.object(PurchaseDraft, "ubah", AsyncMock(return_value=1)) as tulis, \
         patch("repository.audit_log_repository.AuditLogRepository.record", catat):
        await Ctl.ubah_purchase_draft(
            7, {"dpp": 1000000, "description": "Solar industri"}, 9
        )
    assert tulis.await_args.args[1] == {"description": "Solar industri"}
    assert "dpp" not in catat.await_args.kwargs["changes"]


@pytest.mark.asyncio
async def test_kalah_balapan_tidak_dicatat_sebagai_berhasil():
    catat = AsyncMock()
    with patch.object(PurchaseDraft, "get_purchase_draft_by_id",
                      AsyncMock(return_value=_draf())), \
         patch.object(PurchaseDraft, "ubah", AsyncMock(return_value=0)), \
         patch("repository.audit_log_repository.AuditLogRepository.record", catat):
        hasil = await Ctl.ubah_purchase_draft(7, {"dpp": 2500000}, 9)
    assert hasil["status"] == 409 and not catat.called


@pytest.mark.asyncio
async def test_draf_terkonversi_tidak_dapat_dihapus():
    """
    Penjagaannya dahulu berbunyi `isinstance(draf, dict) and ...`, dan
    `fetch_one` tidak pernah mengembalikan dict — jadi draf yang sudah
    menjadi pembelian tetap bisa dihapus, dan pembeliannya kehilangan
    asal-usul angkanya.
    """
    with patch.object(PurchaseDraft, "get_purchase_draft_by_id",
                      AsyncMock(return_value=_draf(convertedAt="2026-09-01"))), \
         patch.object(PurchaseDraft, "delete_purcase_draft", AsyncMock()) as hapus, \
         patch("repository.audit_log_repository.AuditLogRepository.record", AsyncMock()):
        hasil = await Ctl.delete_purchase_draft(7, 1)
    assert hasil["status"] == 409 and not hapus.called


@pytest.mark.asyncio
async def test_periode_terbalik_ditolak_meski_hanya_satu_sisi_dikirim():
    """
    Skema hanya melihat muatannya. Mengirim `periodEnd` saja, pada draf yang
    `periodStart`-nya sudah lebih belakangan, menghasilkan rentang terbalik
    yang tidak akan pernah terjaring penyaringan mana pun.
    """
    with patch.object(PurchaseDraft, "get_purchase_draft_by_id",
                      AsyncMock(return_value=_draf(periodStart="2026-09-20"))), \
         patch.object(PurchaseDraft, "ubah", AsyncMock(return_value=1)) as tulis, \
         patch("repository.audit_log_repository.AuditLogRepository.record", AsyncMock()):
        hasil = await Ctl.ubah_purchase_draft(7, {"periodEnd": "2026-09-01"}, 1)
    assert hasil["status"] == 400 and not tulis.called


@pytest.mark.asyncio
async def test_periode_boleh_dikosongkan_kembali():
    """Null yang DIKIRIM berbeda dari bidang yang tidak dikirim."""
    with patch.object(PurchaseDraft, "get_purchase_draft_by_id",
                      AsyncMock(return_value=_draf(periodStart="2026-09-01",
                                                   periodEnd="2026-09-30"))), \
         patch.object(PurchaseDraft, "ubah", AsyncMock(return_value=1)) as tulis, \
         patch("repository.audit_log_repository.AuditLogRepository.record", AsyncMock()):
        await Ctl.ubah_purchase_draft(
            7, {"periodStart": None, "periodEnd": None}, 1
        )
    assert tulis.await_args.args[1] == {"periodStart": None, "periodEnd": None}
