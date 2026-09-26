"""
Adendum yang mengurangi tidak boleh melampaui yang tersisa.

Adendum berisi selisih. Bila pengurangannya melebihi yang ada, volume
pekerjaan menjadi negatif — keadaan yang tidak berarti apa pun, tidak
memunculkan galat, dan merusak laporan margin tanpa jejak.

Sepadan dengan penjagaan pada pinjaman: `debt` tidak boleh turun di bawah
jumlah yang sudah dibayarkan.
"""

import asyncio
import os

os.environ.setdefault("DATABASE_URL", "mysql://uji:uji@localhost/uji")

from repository.purchase_order_repository import (  # noqa: E402
    PurchaseOrderRepository as R,
)


def _dengan_sisa(sisa_per_task: dict):
    """Ganti pembaca sisa dengan angka tetap, agar tidak perlu basis data."""
    peta = {R._kunci_baris(None, t): v for t, v in sisa_per_task.items()}

    async def palsu(_pid):
        return peta

    R.sisa_volume_induk = staticmethod(palsu)


def _periksa(items):
    return asyncio.run(R.periksa_pengurangan(1, items))


def test_penambahan_selalu_lolos():
    """Adendum yang menambah tidak dibatasi apa pun."""
    _dengan_sisa({"Beton": 100})
    assert _periksa([{"task": "Beton", "quantity": 5}]) == []
    assert _periksa([{"task": "Beton", "quantity": 100000}]) == []


def test_pengurangan_dalam_batas_lolos():
    _dengan_sisa({"Beton": 100})
    assert _periksa([{"task": "Beton", "quantity": -20}]) == []


def test_pengurangan_pas_habis_lolos():
    """Mengurangi seluruh sisanya sah: pekerjaannya dibatalkan seluruhnya."""
    _dengan_sisa({"Beton": 100})
    assert _periksa([{"task": "Beton", "quantity": -100}]) == []


def test_pengurangan_melebihi_sisa_ditolak():
    _dengan_sisa({"Beton": 100})
    m = _periksa([{"task": "Beton", "quantity": -150}])
    assert m and "melebihi sisa" in m[0]


def test_baris_yang_tidak_ada_di_induk_ditolak():
    """
    Baris yang gagal dicocokkan dianggap bersisa nol.

    Pencocokan lewat teks memang tidak sempurna; yang penting ia tidak
    pernah MELONGGARKAN penjagaan.
    """
    _dengan_sisa({"Beton": 100})
    assert _periksa([{"task": "Pekerjaan Baru", "quantity": -1}])


def test_beda_spasi_dan_huruf_tetap_dikenali():
    """
    Perbedaan pengetikan yang tidak berarti tidak boleh membuat baris
    dianggap berbeda — bila dianggap berbeda, pengurangannya tertolak
    padahal sah.
    """
    _dengan_sisa({"Beton fc 25": 100})
    assert _periksa([{"task": "  BETON FC 25  ", "quantity": -50}]) == []


def test_seluruh_baris_bermasalah_dilaporkan():
    """
    Bukan hanya yang pertama.

    Melaporkan satu per satu membuat yang mengisi memperbaiki, mencoba
    lagi, lalu menemukan kesalahan berikutnya.
    """
    _dengan_sisa({"Beton": 100, "Besi": 50})
    m = _periksa(
        [
            {"task": "Beton", "quantity": -999},
            {"task": "Besi", "quantity": -999},
        ]
    )
    assert len(m) == 2


def test_item_id_didahulukan_daripada_teks():
    """`item_id` pasti; teks hanya cadangan bila tidak ada."""
    assert R._kunci_baris(7, "apa pun") == "id:7"
    assert R._kunci_baris(None, "Beton") == "task:beton"
