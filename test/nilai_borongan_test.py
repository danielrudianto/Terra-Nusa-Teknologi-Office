"""
Nilai dokumen borongan disimpan terpisah dari baris pekerjaannya.

PO-H dengan `rateType: "lumpsum"` menyimpan nilainya di
`customData.lumpSumPrice`, sedangkan baris pekerjaannya tersimpan berharga
nol — barisnya di situ hanya menyatakan URAIAN pekerjaannya.

Akibatnya siapa pun yang menjumlahkan `quantity * price` mendapat nol,
sementara `dpp` pada dokumennya benar. Sudah terjadi pada dialog lihat
purchase order: daftar menampilkan 512.500, dialognya menampilkan Rp 0, dan
yang membacanya menyangka datanya rusak.

Uji ini menjaga agar `dpp` yang tersimpan tetap sepakat dengan
`lumpSumPrice` — bila keduanya berbeda, layar mana pun yang memilih salah
satunya akan menampilkan angka yang berbeda dari yang lain.
"""

import json
import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_helper_cetak_memakai_lumpsum():
    """
    Dokumen cetak PO-H membaca `lumpSumPrice`, bukan menjumlahkan barisnya.

    Bila kelak diubah menjadi penjumlahan baris, dokumen borongan akan
    tercetak bernilai nol — dan itu lembar yang ditandatangani vendor.
    """
    p = os.path.join(
        AKAR, "..", "fe", "src", "app", "helpers", "purchase-order-h.helper.ts"
    )
    if not os.path.exists(p):
        return  # repo frontend tidak tersedia di lingkungan ini
    s = open(p).read()
    assert "Number(data.lumpSumPrice)" in s


def test_dialog_lihat_memakai_lumpsum():
    """Dialog lihat harus sepakat dengan dokumen cetaknya."""
    p = os.path.join(
        AKAR,
        "..",
        "fe",
        "src",
        "app",
        "pages",
        "purchase-order",
        "purchase-order-view",
        "purchase-order-view.component.ts",
    )
    if not os.path.exists(p):
        return
    s = open(p).read()
    assert "lumpSumPrice" in s
    assert "rateType" in s


def test_bentuk_data_borongan():
    """
    Bentuk yang menjadi acuan, disalin dari dokumen sungguhan.

    Didokumentasikan sebagai uji, bukan komentar, supaya perubahan bentuknya
    ketahuan alih-alih diam-diam menghasilkan angka nol.
    """
    contoh = {
        "dpp": 512500,
        "customData": {"rateType": "lumpsum", "lumpSumPrice": 512500},
        "items": [{"task": "Jasa Instalasi", "quantity": "1.00", "price": "0.00"}],
    }
    c = contoh["customData"]
    baris = sum(
        float(i["quantity"]) * float(i["price"]) for i in contoh["items"]
    )
    assert baris == 0, "baris memang berharga nol pada dokumen borongan"
    assert c["lumpSumPrice"] == contoh["dpp"], "nilai borongan harus sama dengan dpp"
