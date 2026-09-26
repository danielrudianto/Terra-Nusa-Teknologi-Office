"""
Laporan proyek: draft yang sudah dikonversi TIDAK boleh terhitung dua kali.

Muatan jawabannya sempat menyebut `purchase_drafts` DUA KALI dalam satu dict.
Python memakai yang terakhir, sehingga hasil `get_drafts_by_project` — yang
sengaja mengecualikan draft yang sudah menjadi pembelian — dibuang diam-diam,
dan yang terkirim justru daftar yang menyertakan semuanya.

Tidak ada galat: kunci ganda pada dict bukan kesalahan sintaks, dan keduanya
berbentuk daftar yang sama-sama masuk akal di layar. Yang terlihat hanya biaya
proyek yang lebih besar daripada semestinya — dan ikhtisar margin seluruh
proyek, yang memakai aturan benar, menunjukkan angka lain untuk proyek yang
sama.

Diperiksa dari SUMBERNYA: yang dijaga di sini bentuk muatannya, dan bentuk
muatan sudah dapat dibaca tanpa basis data.
"""

import ast
import inspect
import re

from controllers.purchase_controller import PurchaseController


def _sumber() -> str:
    return inspect.getsource(
        PurchaseController.get_purchase_report_by_project
    )


def test_tidak_ada_kunci_ganda_pada_muatan_jawaban():
    """
    Penjaga yang sesungguhnya.

    Ditelusuri lewat AST, bukan pencocokan teks: kunci ganda bisa ditulis
    berjauhan, dan mencari teksnya akan lolos begitu urutannya berubah.
    """
    pohon = ast.parse(inspect.cleandoc(_sumber()))

    ganda = []
    for simpul in ast.walk(pohon):
        if not isinstance(simpul, ast.Dict):
            continue
        nama = [
            k.value
            for k in simpul.keys
            if isinstance(k, ast.Constant) and isinstance(k.value, str)
        ]
        ganda += [n for n in set(nama) if nama.count(n) > 1]

    assert not ganda, f"kunci disebut lebih dari sekali: {sorted(set(ganda))}"


def test_draft_yang_dikirim_yang_mengecualikan_hasil_konversi():
    """
    Bukan sekadar tidak ganda — yang TERKIRIM harus yang benar.

    `PurchaseRepository.get_drafts_by_project` mengecualikan draft yang sudah
    dikonversi; `PurchaseDraft.get_by_project` tidak. Keduanya sama-sama
    mengembalikan daftar draft, sehingga tertukar tidak menimbulkan galat apa
    pun.
    """
    sumber = _sumber()

    # Nilai yang dipasangkan pada kunci `purchase_drafts`.
    cocok = re.search(r'"purchase_drafts"\s*:\s*(\w+)', sumber)
    assert cocok, "kunci `purchase_drafts` tidak ditemukan lagi pada muatannya"
    assert cocok.group(1) == "drafts", (
        f"yang dikirim `{cocok.group(1)}`; seharusnya `drafts`, hasil "
        f"get_drafts_by_project yang mengecualikan draft terkonversi"
    )


def test_kueri_draft_lama_tidak_lagi_dijalankan():
    """
    Kueri yang hasilnya dibuang tetap membebani basis data.

    Selama kunci gandanya ada, `PurchaseDraft.get_by_project` dijalankan pada
    setiap pembukaan laporan meski hasilnya tertimpa.

    Diperiksa lewat AST, bukan pencarian teks. Percobaan pertama pengujian ini
    mencari namanya di dalam sumber — dan gagal karena nama itu memang
    disebutkan pada KOMENTAR yang menerangkan kekeliruannya. Penjaga yang
    dipicu oleh penjelasannya sendiri tidak menjaga apa pun.
    """
    pohon = ast.parse(inspect.cleandoc(_sumber()))

    dipanggil = set()
    for simpul in ast.walk(pohon):
        if isinstance(simpul, ast.Call) and isinstance(simpul.func, ast.Attribute):
            induk = simpul.func.value
            if isinstance(induk, ast.Name):
                dipanggil.add(f"{induk.id}.{simpul.func.attr}")

    assert "PurchaseDraft.get_by_project" not in dipanggil, sorted(dipanggil)


def test_ringkasan_margin_tak_hitung_draft_terkonversi():
    """
    `ringkasan_margin` menjumlahkan draft LANGSUNG dari SQL — jalur terpisah
    dari payload detail yang dijaga test-test di atas.

    Draft adalah akrual: begitu fakturnya masuk ia DIKONVERSI menjadi
    `purchases` (ditandai `convertedAt`). Tanpa saringan `convertedAt IS NULL`
    di subkueri draft, draft yang sudah dikonversi terjumlah DUA KALI — sekali
    sebagai `beli`, sekali lagi sebagai `draft` — dan margin proyek tampak
    lebih buruk daripada yang sebenarnya. Pernah terjadi; jangan sampai balik.
    """
    from repository.project_repository import ProjectRepository

    sumber = inspect.getsource(ProjectRepository.ringkasan_margin)
    assert "purchase_draft" in sumber, "subkueri draft hilang dari ringkasan_margin"
    assert "convertedAt IS NULL" in sumber, (
        "subkueri draft pada ringkasan_margin HARUS mengecualikan draft yang "
        "sudah dikonversi menjadi pembelian (convertedAt IS NULL) — kalau "
        "tidak, biayanya terhitung dua kali."
    )


def test_muatan_memuat_seluruh_sumber_biaya():
    """Empat sumber yang dibaca layar; hilang satu membuat biayanya kurang."""
    sumber = _sumber()
    for kunci in (
        "purchases",
        "purchase_drafts",
        "reimbursements",
        "sales_invoices",
    ):
        assert f'"{kunci}"' in sumber, kunci


# ---------------------------------------------------------------------------
# Sumber yang kosong bukan galat
# ---------------------------------------------------------------------------
#
# Repositori laporan mengembalikan 404 ketika tidak menemukan baris — bentuk
# yang masuk akal bagi rute "ambil satu dokumen", tetapi keliru bagi laporan:
# proyek yang belum berbelanja bukan proyek yang tidak ditemukan.
#
# Akibatnya nyata: proyek KBPDP punya penjualan Rp 240 juta dan belum punya
# pembelian sama sekali. Yang tampil hanya spanduk merah "No purchases found",
# dan penjualannya — satu-satunya angka yang ada — ikut hilang.

import pytest
from fastapi import HTTPException

from controllers.purchase_controller import _daftar_atau_kosong


def test_tidak_ada_baris_menjadi_daftar_kosong():
    kosong = {"error": "No purchases found for this project", "status": 404}
    assert _daftar_atau_kosong(kosong, "pembelian") == []


def test_daftar_yang_terisi_diteruskan_apa_adanya():
    isi = [{"id": 1}, {"id": 2}]
    assert _daftar_atau_kosong(isi, "pembelian") == isi


def test_daftar_kosong_sungguhan_tetap_daftar_kosong():
    assert _daftar_atau_kosong([], "pembelian") == []
    assert _daftar_atau_kosong(None, "pembelian") == []


@pytest.mark.parametrize("status", [400, 500])
def test_galat_sungguhan_TETAP_dilemparkan(status):
    """
    Inti pembedaannya.

    Kueri yang gagal lalu ditampilkan sebagai "tidak ada biaya" membuat
    laporan menyatakan margin penuh atas proyek yang justru datanya tidak
    terbaca — dan tidak ada satu pun tanda di layar yang membedakannya dari
    proyek yang memang belum berbelanja.
    """
    galat = {"error": "Internal server error.", "status": status}
    with pytest.raises(HTTPException) as e:
        _daftar_atau_kosong(galat, "pembelian")
    assert e.value.status_code == status


def test_laporan_tidak_lagi_melempar_untuk_sumber_kosong():
    """
    Penjaga terhadap pemeriksaan lama yang melempar apa pun galatnya.

    Bentuk `if "error" in x: raise` pada sumber laporan adalah persis yang
    menggugurkan seluruh laporan hanya karena satu sumber kosong.
    """
    sumber = _sumber()
    assert 'raise HTTPException(status_code=purchases["status"]' not in sumber
    assert 'raise HTTPException(status_code=sales_invoices["status"]' not in sumber
    assert 'raise HTTPException(status_code=reimbursements["status"]' not in sumber
