"""
MASA PAJAK pembelian.

Laporan PPN mengelompokkan pembelian menurut bulan PENGKREDITAN PPN
masukannya, bukan menurut tanggal dokumennya. Keduanya kerap berbeda:
pemasok menerbitkan faktur pajak bulan Juli atas invoice bulan Juni, dan
yang menentukan dokumen itu masuk SPT mana adalah fakturnya.

Yang dijaga di sini adalah keputusan-keputusan yang mudah terbalik saat
berkasnya disentuh lagi. Masing-masing menghasilkan laporan yang tampak
wajar tetapi salah — dan angka yang salah pada laporan pajak tidak
menimbulkan galat apa pun. Ia baru ketahuan ketika SPT-nya diperiksa.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(AKAR, "repository", "purchase_repository.py")
MODEL = os.path.join(AKAR, "models", "purchase_model.py")


def _blok(nama: str) -> str:
    s = open(REPO, encoding="utf-8").read()
    i = s.index(f"async def {nama}(")
    j = s.find("\n    @staticmethod", i)
    return s[i:] if j == -1 else s[i:j]


def test_kolom_masa_pajak_boleh_kosong():
    """
    NULL berarti "ikut tanggal dokumen".

    Seluruh baris lama bernilai NULL. Bila kolomnya wajib diisi, migrasinya
    harus menebak masa pajak ribuan dokumen historis — dan tebakan itu
    langsung menjadi angka laporan yang tidak pernah diputuskan siapa pun.
    """
    s = open(MODEL, encoding="utf-8").read()
    m = re.search(r'Column\("taxPeriod",\s*Date\(\),\s*nullable=(\w+)\)', s)
    assert m, "kolom taxPeriod tidak ada pada model"
    assert m.group(1) == "True", "taxPeriod harus boleh kosong"


def test_arti_masa_pajak_ditulis_satu_kali():
    """
    `COALESCE(taxPeriod, date)` berada di SATU tempat.

    Menyalinnya ke tiap kueri membuat keduanya berselisih pada perubahan
    berikutnya, dan yang tertinggal tidak menimbulkan galat: hanya satu
    laporan yang diam-diam mengelompokkan menurut tanggal dokumen sementara
    laporan di sebelahnya memakai masa pajak.
    """
    s = open(REPO, encoding="utf-8").read()
    assert "def masa_pajak_efektif(" in s, "pembantu masa pajak tidak ada"
    # Hanya boleh ada satu tempat yang benar-benar menyusun COALESCE-nya.
    penyusun = re.findall(
        r"func\.coalesce\(\s*purchases_table\.c\.taxPeriod", s
    )
    assert len(penyusun) == 1, (
        f"COALESCE(taxPeriod, date) ditulis {len(penyusun)} kali; "
        "seharusnya hanya di dalam masa_pajak_efektif()"
    )


def test_rincian_ppn_dikelompokkan_menurut_masa_pajak():
    """
    Bila ini kembali memakai `purchases_table.c.date`, faktur Juli atas
    invoice Juni tercatat pada masa Juni — dan daftar rincian SPT Juli
    kehilangan barisnya tanpa satu pun tanda.
    """
    blok = _blok("get_ppn_report")
    assert "masa_pajak_efektif()" in blok, (
        "get_ppn_report tidak memakai masa pajak"
    )
    assert not re.search(
        r"extract\(\s*['\"](month|year)['\"],\s*purchases_table\.c\.date\s*\)",
        blok,
    ), "get_ppn_report masih menyaring menurut tanggal dokumen"


def test_agregat_bulanan_memakai_dasar_yang_sama():
    """
    Peta PPN kreditable per bulan menyusun saldo kompensasi antar masa.

    Bila ia memakai tanggal dokumen sementara rinciannya memakai masa
    pajak, saldo yang tampil di atas tidak akan pernah cocok dengan jumlah
    baris di bawahnya — dan selisihnya terbaca sebagai kesalahan hitung,
    bukan sebagai dua dasar pengelompokan yang berbeda.
    """
    blok = _blok("get_ppn_masukan_kreditable_bulanan")
    assert "masa_pajak_efektif()" in blok, (
        "agregat bulanan tidak memakai masa pajak"
    )
    assert not re.search(r'func\.extract\(\s*"year",\s*p\.date\s*\)', blok), (
        "agregat bulanan masih memakai tanggal dokumen"
    )


def test_batas_masa_sebelumnya_ikut_masa_pajak():
    """
    Batas "masa-masa SEBELUM yang dipilih" menentukan saldo lebih bayar yang
    terbawa. Memakai tanggal dokumen di sini sementara pengelompokannya
    memakai masa pajak membuat satu dokumen terhitung pada masa berjalan
    DAN ikut masuk saldo bawaan — nilainya dihitung dua kali.
    """
    s = open(REPO, encoding="utf-8").read()
    assert "p.date < end_date" not in s, (
        "batas masa sebelumnya masih memakai tanggal dokumen"
    )
    assert "masa < end_date" in s, "batas masa sebelumnya tidak memakai masa pajak"


def test_rekap_bulanan_tetap_memakai_tanggal_dokumen():
    """
    Rekap pembelian bulanan BUKAN laporan pajak.

    Ia menjawab "pembelian apa saja yang terjadi bulan ini", dan jawabannya
    memang tanggal dokumennya. Menggesernya ke masa pajak akan memindahkan
    pembelian Juni ke rekap Juli hanya karena fakturnya terlambat — dan
    rekap itu dipakai membandingkan dengan pengeluaran, bukan dengan SPT.
    """
    blok = _blok("get_monthly_recap")
    assert "masa_pajak_efektif" not in blok, (
        "rekap bulanan ikut bergeser ke masa pajak; seharusnya tetap "
        "memakai tanggal dokumen"
    )
