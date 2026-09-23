"""
Alat SEMENTARA: tautkan pembelian lama ke CoP.

Yang dijaga: tautan tidak boleh menyatakan tagihan orang lain, tidak boleh
menimpa tautan yang sudah ada, dan hanya berlaku untuk CoP yang memang siap
ditagih. Selisih nilai DILAPORKAN, bukan ditolak — data historis memang
kerap tidak bulat, dan itu keputusan pemilik.
"""
from unittest.mock import AsyncMock, patch

import pytest

import repository.tautan_pembelian_repository as t
from repository.tautan_pembelian_repository import (
    TautanPembelianController as Ctl,
    TautanPembelianRepository as Repo,
)


COP = {"id": 7, "supplierID": 42, "purchaseOrderID": 9, "netAmount": 450000}


def _cop(**ganti):
    return {**COP, **ganti}


@pytest.mark.asyncio
async def test_cop_belum_disetujui_ditolak():
    from controllers.certificate_of_payment_controller import (
        CertificateOfPaymentController as CoP,
    )
    from repository.certificate_of_payment_repository import (
        CertificateOfPaymentRepository as CoPRepo,
    )
    with patch.object(CoPRepo, "get_by_id", AsyncMock(return_value=_cop())), \
         patch.object(CoP, "periksa_boleh_ditagih",
                      AsyncMock(return_value={"error": "belum disetujui", "status": 409})), \
         patch.object(Repo, "tautkan", AsyncMock()) as pasang:
        hasil = await Ctl.tautkan(7, 100)
    assert hasil["status"] == 409 and not pasang.called


@pytest.mark.asyncio
async def test_pemasok_beda_ditolak():
    from controllers.certificate_of_payment_controller import (
        CertificateOfPaymentController as CoP,
    )
    from repository.certificate_of_payment_repository import (
        CertificateOfPaymentRepository as CoPRepo,
    )
    beli = {"id": 100, "invoiceName": "INV-1", "supplierID": 43, "dpp": 450000,
            "certificateOfPaymentID": None, "isDelete": 0}
    with patch.object(CoPRepo, "get_by_id", AsyncMock(return_value=_cop())), \
         patch.object(CoP, "periksa_boleh_ditagih", AsyncMock(return_value=None)), \
         patch.object(Repo, "pembelian", AsyncMock(return_value=beli)), \
         patch.object(Repo, "tautkan", AsyncMock()) as pasang:
        hasil = await Ctl.tautkan(7, 100)
    assert hasil["status"] == 409 and not pasang.called


@pytest.mark.asyncio
async def test_pembelian_sudah_tertaut_ditolak():
    from controllers.certificate_of_payment_controller import (
        CertificateOfPaymentController as CoP,
    )
    from repository.certificate_of_payment_repository import (
        CertificateOfPaymentRepository as CoPRepo,
    )
    beli = {"id": 100, "invoiceName": "INV-1", "supplierID": 42, "dpp": 450000,
            "certificateOfPaymentID": 5, "isDelete": 0}
    with patch.object(CoPRepo, "get_by_id", AsyncMock(return_value=_cop())), \
         patch.object(CoP, "periksa_boleh_ditagih", AsyncMock(return_value=None)), \
         patch.object(Repo, "pembelian", AsyncMock(return_value=beli)), \
         patch.object(Repo, "tautkan", AsyncMock()) as pasang:
        hasil = await Ctl.tautkan(7, 100)
    assert hasil["status"] == 409 and not pasang.called


@pytest.mark.asyncio
async def test_selisih_dilaporkan_bukan_ditolak():
    from controllers.certificate_of_payment_controller import (
        CertificateOfPaymentController as CoP,
    )
    from repository.certificate_of_payment_repository import (
        CertificateOfPaymentRepository as CoPRepo,
    )
    beli = {"id": 100, "invoiceName": "INV-1", "supplierID": 42, "dpp": 500000,
            "certificateOfPaymentID": None, "isDelete": 0}
    with patch.object(CoPRepo, "get_by_id", AsyncMock(return_value=_cop())), \
         patch.object(CoP, "periksa_boleh_ditagih", AsyncMock(return_value=None)), \
         patch.object(Repo, "pembelian", AsyncMock(return_value=beli)), \
         patch.object(Repo, "tautkan", AsyncMock(return_value=1)):
        hasil = await Ctl.tautkan(7, 100)
    assert hasil == {"tertaut": True, "selisih": 50000.0}


@pytest.mark.asyncio
async def test_kalah_balapan_tidak_dianggap_berhasil():
    from controllers.certificate_of_payment_controller import (
        CertificateOfPaymentController as CoP,
    )
    from repository.certificate_of_payment_repository import (
        CertificateOfPaymentRepository as CoPRepo,
    )
    beli = {"id": 100, "invoiceName": "INV-1", "supplierID": 42, "dpp": 450000,
            "certificateOfPaymentID": None, "isDelete": 0}
    with patch.object(CoPRepo, "get_by_id", AsyncMock(return_value=_cop())), \
         patch.object(CoP, "periksa_boleh_ditagih", AsyncMock(return_value=None)), \
         patch.object(Repo, "pembelian", AsyncMock(return_value=beli)), \
         patch.object(Repo, "tautkan", AsyncMock(return_value=0)):
        hasil = await Ctl.tautkan(7, 100)
    assert hasil["status"] == 409


@pytest.mark.asyncio
async def test_pemasok_dibaca_dari_spk_bila_cop_lama_kosong():
    with patch.object(t.database, "fetch_one", AsyncMock(return_value={"supplierID": 42})):
        assert await Repo.pemasok_cop(_cop(supplierID=None)) == 42


@pytest.mark.asyncio
async def test_calon_menyaring_pemasok_dan_yang_belum_tertaut():
    with patch.object(t.database, "fetch_all", AsyncMock(return_value=[])) as f:
        await Repo.calon(7, 42, "INV")
    sql, params = f.await_args.args[0], f.await_args.args[1]
    assert "p.supplierID = :pemasok" in sql
    assert "p.certificateOfPaymentID IS NULL" in sql
    assert "p.isDelete = 0" in sql
    assert params["pemasok"] == 42 and params["kata"] == "%INV%"


@pytest.mark.asyncio
async def test_lepas_hanya_untuk_tautan_cop_ini():
    with patch.object(t.database, "execute", AsyncMock(return_value=0)) as ex:
        hasil = await Ctl.lepas(7, 100)
    sql = ex.await_args.args[0]
    assert "certificateOfPaymentID = :cop" in sql
    assert hasil["status"] == 409


def test_tanpa_jejak_audit_dan_tanpa_kolom_baru():
    """Permintaan pemilik: fitur ini harus dapat dicopot tanpa sisa."""
    isi = open(t.__file__, encoding="utf-8").read()
    # Tidak ada penulisan jejak audit sama sekali (penyebutan di catatan
    # berkas tidak dihitung — yang dilarang panggilannya).
    for panggilan in ("audit_logs", "catat_audit", "AuditLogRepository"):
        assert panggilan not in isi, panggilan
    # Tidak ada kolom atau tabel baru: tautannya memakai kolom yang sudah ada.
    assert "ALTER TABLE" not in isi and "CREATE TABLE" not in isi
    assert "certificateOfPaymentID" in isi
