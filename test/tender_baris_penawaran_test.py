"""
Menyunting tender yang sudah punya penawaran.

GEJALA YANG DILAPORKAN: "edit tender, error message-nya muncul tapi datanya
bisa berubah."

SEBABNYA: kepala tender disimpan lebih dahulu dan langsung commit, lalu
seluruh baris permintaan DIHAPUS KERAS untuk ditulis ulang. Penghapusan itu
ditolak kunci asing `fk_tqi_item` begitu ada penawaran yang menghargai
barisnya, dan pengecualiannya menjadi galat 500 — sesudah kepala tendernya
terlanjur tersimpan.

Dua hal yang dijaga di sini: barisnya diselaraskan (bukan dihapus lalu
ditulis ulang), dan baris yang sudah dihargai tidak dapat hilang diam-diam
bersama harganya.
"""
from unittest.mock import AsyncMock, patch

import pytest

import repository.tender_repository as tr
from repository.tender_repository import TenderRepository as Repo


def _baris(*ids):
    return [{"id": i, "name": f"Baris {i}"} for i in ids]


class Jejak:
    """Catat kueri yang dijalankan, dan jawab pembacaan seperlunya."""

    def __init__(self, id_lama, terpakai):
        self.id_lama = id_lama
        self.terpakai = terpakai
        self.dijalankan = []

    async def fetch_all(self, kueri, nilai=None):
        teks = str(kueri)
        if "tender_quote_items" in teks:
            return [{"id": i} for i in self.terpakai]
        if "name" in teks and "IN" in teks:
            return [{"name": f"Baris {i}"} for i in self.id_lama]
        return [{"id": i} for i in self.id_lama]

    async def execute(self, kueri, nilai=None):
        self.dijalankan.append(str(kueri))
        return 1


async def _jalankan(id_lama, terpakai, kiriman):
    j = Jejak(id_lama, terpakai)
    with patch.object(tr.database, "fetch_all", AsyncMock(side_effect=j.fetch_all)), \
         patch.object(tr.database, "execute", AsyncMock(side_effect=j.execute)):
        hasil = await Repo._tulis_baris(7, kiriman)
    return hasil, j


@pytest.mark.asyncio
async def test_baris_yang_sudah_dihargai_tidak_ikut_terhapus():
    """
    Inti keluhannya. Baris 1 dihargai vendor dan dihilangkan dari kiriman;
    dahulu ia terhapus (atau penghapusannya melempar 500 setelah kepala
    tendernya tersimpan). Sekarang permintaannya ditolak dengan menyebut
    barisnya.
    """
    hasil, j = await _jalankan([1, 2], {1}, _baris(2))
    assert hasil and hasil["status"] == 409
    assert not any("DELETE" in q.upper() for q in j.dijalankan)


@pytest.mark.asyncio
async def test_pesannya_menyebut_baris_yang_menahan():
    hasil, _ = await _jalankan([1, 2], {1}, _baris(2))
    assert "Baris 1" in hasil["error"]


@pytest.mark.asyncio
async def test_baris_yang_dikirim_diperbarui_bukan_dihapus_lalu_disisipkan():
    """
    Diperbarui DI TEMPAT, supaya `tender_quote_items` tetap menunjuk baris
    yang sama dan harga yang sudah ditawarkan tidak kehilangan induknya.
    """
    hasil, j = await _jalankan([1, 2], {1, 2}, _baris(1, 2))
    assert hasil is None
    assert not any("DELETE" in q.upper() for q in j.dijalankan)
    assert sum("UPDATE" in q.upper() for q in j.dijalankan) == 2
    assert not any("INSERT" in q.upper() for q in j.dijalankan)


@pytest.mark.asyncio
async def test_baris_tanpa_id_disisipkan_sebagai_baris_baru():
    hasil, j = await _jalankan([1], {1}, _baris(1) + [{"name": "Baru"}])
    assert hasil is None
    assert sum("INSERT" in q.upper() for q in j.dijalankan) == 1


@pytest.mark.asyncio
async def test_baris_belum_dihargai_boleh_dihapus():
    """Yang belum disentuh penawaran tetap dapat dibuang seperti biasa."""
    hasil, j = await _jalankan([1, 2], set(), _baris(2))
    assert hasil is None
    assert any("DELETE" in q.upper() for q in j.dijalankan)


@pytest.mark.asyncio
async def test_ubah_tender_dibungkus_satu_transaksi():
    """
    Kepala tender dan baris permintaannya ditulis ke DUA tabel. Tanpa
    transaksi, kegagalan pada yang kedua meninggalkan yang pertama
    tersimpan — dan itulah bentuk persis keluhan "error tapi datanya
    berubah".

    Diperiksa di sini, bukan hanya dipercayakan pada pembacaan mata:
    mencopot `@atomik` tidak menjatuhkan satu pun uji lain.
    """
    from controllers.tender_controller import TenderController

    fungsi = TenderController.ubah
    # `@atomik` membungkus fungsinya; pembungkusnya membawa nama aslinya
    # lewat `functools.wraps`, jadi yang diperiksa penandanya.
    assert getattr(fungsi, "__atomik__", False), (
        "TenderController.ubah harus dibungkus @atomik — menulis ke tenders "
        "dan tender_items dalam satu tindakan."
    )
