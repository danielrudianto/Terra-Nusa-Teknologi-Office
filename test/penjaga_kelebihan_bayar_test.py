"""
Penjaga kelebihan bayar harus mengenali SETIAP jenis dokumen.

`_sisa_tagihan` adalah satu-satunya penjaga di sisi server yang menolak
pembayaran atas dokumen yang sudah lunas dan pembayaran yang melebihi
sisanya. Ia memilih cabang menurut jenis dokumennya, dan cabang yang tidak
ada menjawab `None` — yang oleh pemanggilnya diperlakukan sebagai "tidak
dapat diperiksa", lalu seluruh penjagaannya dilewati.

Kegagalannya karena itu SUNYI dan hanya menyangkut satu jenis dokumen. Slip
gaji tidak punya cabang sama sekali: slip yang sama dapat dibayar dua kali,
keduanya disetujui, uangnya keluar dua kali — lalu penyelarasan status lunas
menghitung selisihnya sebesar satu kali gaji, menyimpulkan slipnya BELUM
LUNAS, dan daftarnya menampilkan chip "belum dibayar". Orang berikutnya
membayarnya untuk ketiga kalinya.

Satu-satunya penjaga sebelum ini ada di layar, dan layar bukan pengamanan.

Diperiksa lewat AST, bukan dengan menjalankan pembayaran sungguhan: yang
dijaga adalah TIDAK ADANYA jenis dokumen yang terlewat — termasuk jenis yang
ditambahkan besok.
"""

import ast
import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JALUR = os.path.join(AKAR, "controllers", "payment_outgoing_controller.py")


def _sumber() -> str:
    return open(JALUR, encoding="utf-8").read()


def _fungsi(nama: str) -> ast.AST:
    pohon = ast.parse(_sumber())
    for simpul in ast.walk(pohon):
        if isinstance(simpul, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if simpul.name == nama:
                return simpul
    raise AssertionError(f"fungsi `{nama}` tidak ditemukan")


def _kunci_dokumen(simpul: ast.AST) -> set:
    """Nama dokumen yang disebut `payment_data.get("...")` di dalam fungsi."""
    hasil = set()
    for n in ast.walk(simpul):
        if not isinstance(n, ast.Call):
            continue
        if not isinstance(n.func, ast.Attribute) or n.func.attr != "get":
            continue
        if not n.args or not isinstance(n.args[0], ast.Constant):
            continue
        nilai = n.args[0].value
        if isinstance(nilai, str) and nilai.endswith("ID"):
            hasil.add(nilai)
    return hasil


#: Jenis dokumen yang dapat dibayar. Diambil dari kolom `payments_outgoing`.
JENIS_DOKUMEN = {
    "purchaseID",
    "expenseID",
    "reimbursementID",
    "salarySlipID",
    "loanID",
}


def test_sisa_tagihan_mengenali_setiap_jenis_dokumen():
    disebut = _kunci_dokumen(_fungsi("_sisa_tagihan"))
    kurang = sorted(JENIS_DOKUMEN - disebut)
    assert not kurang, (
        f"`_sisa_tagihan` tidak punya cabang untuk {kurang}. "
        "Cabang yang hilang menjawab None, dan SELURUH penjaga kelebihan "
        "bayar dilewati untuk jenis dokumen itu — tanpa galat, tanpa jejak."
    )


def test_slip_gaji_dinilai_dengan_rumus_bersama():
    """
    Cabang gaji harus memakai `nilai_slip`, bukan menjumlahkan sendiri.

    Rumus itu pernah disalin mentah dua kali di berkas ini, dan salinannya
    menjumlahkan kolomnya tanpa `or 0` — satu tunjangan NULL membuat
    persetujuan pembayaran gagal tanpa menyebut sebabnya.
    """
    fungsi = _fungsi("_sisa_tagihan")
    sumber = ast.get_source_segment(_sumber(), fungsi) or ""
    i = sumber.find('payment_data.get("salarySlipID")')
    assert i != -1, "cabang slip gaji tidak ditemukan"
    # Sampai cabang berikutnya, bukan sekian aksara: panjang cabangnya
    # berubah setiap kali keterangannya ditulis ulang.
    j = sumber.find("payment_data.get(", i + 1)
    cabang = sumber[i:] if j == -1 else sumber[i:j]
    assert "nilai_slip(" in cabang, (
        "cabang slip gaji tidak memakai `nilai_slip()`; rumusnya disalin lagi"
    )


def test_penyelarasan_dan_penjaga_memakai_penilai_yang_sama():
    """
    Yang menolak pembayaran dan yang menyimpulkan lunas harus sepakat.

    Kalau penjaga memakai satu rumus dan penyelarasan memakai rumus lain,
    sistem dapat menerima pembayaran lalu langsung menyatakan dokumennya
    belum lunas — persis keadaan yang membuat slip dibayar berulang.
    """
    s = _sumber()
    for nama in ("_sisa_tagihan", "selaraskan_status_lunas"):
        fungsi = _fungsi(nama)
        cuplik = ast.get_source_segment(s, fungsi) or ""
        assert "nilai_slip(" in cuplik, f"`{nama}` tidak memakai `nilai_slip()`"
