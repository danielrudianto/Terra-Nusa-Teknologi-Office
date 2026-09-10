"""
Daftar rekening bank: cari, urut, hitung, dan penjaga saldo saat dihapus.

Tiga kekeliruan pertama berasal dari satu fungsi yang sama
(`BankAccount.get_banks`) dan ketiganya gagal dengan diam:

  * `keyword` diterima rutenya lalu tidak pernah dipakai — kotak pencarian
    mengirim kata kuncinya dan hasilnya tidak pernah berubah.
  * kolom pengurut dihitung ke dalam `_urut` lalu diabaikan; kueri yang
    dijalankan selalu mengurut menurut nomor rekening, sehingga mengklik
    kepala kolom tidak melakukan apa pun.
  * penghitung halaman menyaring `isDelete == False` sementara kueri datanya
    TIDAK — paginator menyebut satu angka, tabelnya menampilkan angka lain,
    dan rekening yang sudah dihapus tetap muncul.

Yang keempat lain jenisnya: rekening bersaldo tidak boleh dihapus. Saldo
adalah uang yang masih ada; menghapus rekeningnya mengeluarkannya dari saldo
gabungan dan kalender kas sementara uangnya tetap di bank.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _blok(relatif: str, nama: str) -> str:
    """Badan sebuah fungsi, tanpa komentar."""
    s = open(os.path.join(AKAR, relatif), encoding="utf-8").read()
    i = s.index(f"async def {nama}(")
    j = s.find("async def ", i + 10)
    blok = s[i:] if j == -1 else s[i:j]
    return "\n".join(
        b for b in blok.splitlines() if not b.lstrip().startswith("#")
    )


REPO = "repository/bank_account_repository.py"
CTRL = "controllers/bank_controller.py"


# ----------------------------------------------------------------------
# get_banks
# ----------------------------------------------------------------------

def test_kata_kunci_benar_benar_dipakai():
    b = _blok(REPO, "get_banks")
    assert "keyword" in b, "get_banks tidak menerima kata kunci"
    assert re.search(r"\.like\(", b), (
        "kata kunci diterima tetapi tidak pernah masuk ke kueri"
    )


def test_pencarian_mencakup_ketiga_kolom_yang_terlihat():
    """
    Yang mengetik di kotak pencarian tidak tahu kolom mana yang dicari.

    Mencari hanya pada satu kolom membuat pencarian tampak rusak justru
    ketika kata kuncinya benar — nama rekening ketemu, nomornya tidak.
    """
    b = _blok(REPO, "get_banks")
    for kolom in ("bankName", "bankAccountName", "bankAccountNumber"):
        assert re.search(rf"c\.{kolom}\.like\(", b), (
            f"pencarian tidak mencakup {kolom}"
        )


def test_kolom_pengurut_benar_benar_dipakai():
    b = _blok(REPO, "get_banks")
    urut = re.findall(r"order_by\(([^)]*)\)", b)
    assert urut, "get_banks tidak mengurut sama sekali"
    assert any("_urut" in u for u in urut), (
        "kolom pengurut dihitung lalu diabaikan; kueri yang dijalankan "
        "mengurut menurut kolom tetap, sehingga kepala kolom tidak berfungsi"
    )


def test_hitungan_dan_isinya_memakai_syarat_yang_sama():
    """
    Ini yang membuat paginator menyebut angka yang berbeda dari isi tabel.

    Selama syaratnya disusun dua kali, salah satunya cepat atau lambat
    tertinggal ketika penyaringnya disesuaikan.
    """
    b = _blok(REPO, "get_banks")
    assert b.count("where(*syarat)") >= 2, (
        "kueri data dan kueri hitung tidak memakai daftar syarat yang sama"
    )
    assert "isDelete == False" not in b.split("func.count()")[-1], (
        "kueri hitung masih menyaring sendiri, terlepas dari kueri datanya"
    )


def test_bawaannya_hanya_rekening_yang_belum_dihapus():
    b = _blok(REPO, "get_banks")
    assert re.search(r'keadaan.*=\s*"aktif"', b), (
        "keadaan bawaannya bukan 'aktif'; rekening terhapus akan ikut "
        "muncul pada pemuatan pertama"
    )
    for keadaan in ("aktif", "dihapus", "semua"):
        assert f'"{keadaan}"' in b, f"keadaan '{keadaan}' tidak ditangani"


# ----------------------------------------------------------------------
# Penjaga saldo
# ----------------------------------------------------------------------

def test_rekening_bersaldo_tidak_dapat_dihapus():
    b = _blok(CTRL, "delete_bank_account")
    assert "fetch_by_bank_account_ids" in b, (
        "penghapusan rekening tidak memeriksa saldonya"
    )
    assert "BANK_HAS_BALANCE" in b, (
        "penolakannya tidak memakai kode tetap, sehingga layar tidak dapat "
        "menerjemahkannya menjadi kalimat yang berguna"
    )


def test_saldo_diperiksa_SEBELUM_dihapus():
    b = _blok(CTRL, "delete_bank_account")
    i_periksa = b.index("fetch_by_bank_account_ids")
    i_hapus = b.index("BankAccount.delete_bank_account(")
    assert i_periksa < i_hapus, (
        "saldo diperiksa setelah rekeningnya dihapus"
    )


def test_gagal_membaca_saldo_menahan_penghapusan():
    """
    Menolak penghapusan yang mungkin sah lebih ringan akibatnya daripada
    menghilangkan rekening yang ternyata masih berisi.
    """
    b = _blok(CTRL, "delete_bank_account")
    assert "BANK_BALANCE_UNKNOWN" in b, (
        "kegagalan membaca saldo diperlakukan seolah saldonya nol"
    )


def test_nol_tidak_terbaca_sebagai_bersaldo():
    """
    Saldo tersimpan DECIMAL; nol dapat datang sebagai 0.0 atau 0.0000.
    Perbandingan yang terlalu ketat menahan penghapusan rekening kosong.
    """
    b = _blok(CTRL, "delete_bank_account")
    assert re.search(r"abs\(nilai\)\s*>\s*0\.5", b), (
        "ambang saldonya tidak memberi kelonggaran pembulatan"
    )
