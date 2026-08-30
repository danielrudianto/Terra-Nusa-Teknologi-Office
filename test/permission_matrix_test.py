"""
Pengujian matriks izin dan pemetaan divisi.

Yang diuji di sini bukan mesinnya, melainkan KEBIJAKANNYA: siapa boleh
melakukan apa. Nilai-nilai pada matriks mudah diubah tanpa disadari
akibatnya — satu angka bergeser dan seorang staf tiba-tiba dapat menghapus
rekening bank.

Pengujian ini menjaga keputusan yang sudah diambil, sehingga perubahannya
harus disengaja: bila ada yang gagal, itu pertanda kebijakannya berubah, dan
perubahan itu perlu dibaca ulang sebelum pengujiannya disesuaikan.
"""

from pathlib import Path

import pytest

from constants.department_modules import (
    DEPARTMENT_LABELS,
    DEPARTMENT_MODULES,
    DEPARTMENT_READ_ONLY,
    UMUM,
    modules_for,
)
from constants.permission_matrix import (
    ACTIONS,
    MATRIX,
    NOT_APPLICABLE,
    SPECIAL_ONLY,
    required_level,
)


def boleh(level: int, departments: set[str], module: str, action: str) -> bool:
    """
    Tiruan dari `utils.permission.is_allowed`, tanpa menyentuh basis data.

    Ditulis ulang di sini dengan sengaja: yang diuji adalah kebijakannya,
    bukan pembacaan tabel izin khusus dan departemen dari MySQL.
    """
    if level < 5 and departments and module not in modules_for(departments):
        return False
    minimum = required_level(module, action)
    if minimum in (NOT_APPLICABLE, SPECIAL_ONLY):
        return False
    return level >= minimum


# ---------------------------------------------------------------------------
# Bentuk matriks
# ---------------------------------------------------------------------------


def test_setiap_modul_punya_lima_nilai():
    for module, nilai in MATRIX.items():
        assert len(nilai) == len(ACTIONS), f"{module} tidak punya {len(ACTIONS)} nilai"


def test_nilai_matriks_dalam_rentang_yang_dikenali():
    sah = {NOT_APPLICABLE, SPECIAL_ONLY, 1, 2, 3, 4, 5}
    for module, nilai in MATRIX.items():
        for aksi, v in zip(ACTIONS, nilai):
            assert v in sah, f"{module}:{aksi} bernilai {v}"


def test_semua_tingkat_dipakai():
    """
    Tingkat yang tidak pernah muncul berarti tidak berarti apa-apa.

    Level 4 pernah tidak dipakai sama sekali, sehingga General Manager persis
    sama dengan Manager — dan tidak ada yang menyadarinya karena tidak ada
    yang memeriksa.
    """
    dipakai = {v for nilai in MATRIX.values() for v in nilai}
    for tingkat in (1, 2, 3, 4, 5):
        assert tingkat in dipakai, f"tingkat {tingkat} tidak pernah dipakai"


def test_membaca_tidak_lebih_sulit_daripada_mengubah():
    """Yang boleh mengubah pasti boleh melihat."""
    for module, nilai in MATRIX.items():
        baca = nilai[ACTIONS.index("read")]
        for aksi in ("create", "update", "delete"):
            v = nilai[ACTIONS.index(aksi)]
            if v in (NOT_APPLICABLE, SPECIAL_ONLY) or baca in (
                NOT_APPLICABLE,
                SPECIAL_ONLY,
            ):
                continue
            assert baca <= v, f"{module}: {aksi} ({v}) lebih longgar dari read ({baca})"


# ---------------------------------------------------------------------------
# Kebijakan yang dijaga
# ---------------------------------------------------------------------------


def test_rekening_bank_hanya_pemilik_usaha():
    """Menambah dan menghapus rekening menyangkut uang perusahaan langsung."""
    for aksi in ("create", "update", "delete"):
        assert required_level("bank", aksi) == 5


def test_mutasi_bank_dapat_dilihat_bagian_keuangan():
    """Mencocokkan buku bank pekerjaan rutin, bukan kewenangan direksi."""
    assert required_level("bank", "read") == 3


def test_pinjaman_hanya_pemilik_usaha():
    for aksi in ("create", "update", "delete", "approve"):
        assert required_level("loan", aksi) == 5


def test_persetujuan_pembayaran_di_atas_pembuatannya():
    """
    Yang menyiapkan uang bukan yang mengizinkan.

    Jaraknya boleh berubah, tetapi menyetujui tidak boleh menjadi lebih mudah
    daripada membuat.
    """
    buat = required_level("payment_outgoing", "create")
    setuju = required_level("payment_outgoing", "approve")
    assert setuju > buat


def test_jejak_aktivitas_terbuka_tetapi_isinya_dibatasi():
    """
    Halaman aktivitas boleh dibuka semua level; isinya yang dibatasi.

    Di bawah level 5 yang terlihat hanya aktivitas sendiri, dan pembatasan
    itu ada di `audit_log_routes.py` — matriks hanya mengenal "boleh membuka
    atau tidak", sehingga tidak dapat menyatakannya.

    Uji ini menjaga dua hal sekaligus: halamannya memang terbuka, DAN
    penjaganya masih ada di rutenya. Yang kedua penting karena membuka
    matriks tanpa penjaga akan memberi seluruh level akses ke perubahan gaji.
    """
    assert required_level("audit_log", "read") == 1

    rute = (Path(__file__).resolve().parents[1] / "routes" / "audit_log_routes.py").read_text()
    assert "if level < 5:" in rute, "penjaga level hilang dari rute audit"
    assert 'userID = [current_user["id"]]' in rute, "pemaksaan ke diri sendiri hilang"


def test_modul_wilayah_mutlak_memuat_gaji_dan_karyawan():
    """
    Gaji dan data karyawan tidak pernah terbuka lewat level saja.

    Level 4 sengaja tidak diberi departemen — jabatannya General Manager,
    wilayahnya seluruh perusahaan. Tanpa penjagaan terpisah, ia membaca gaji
    seluruh karyawan tanpa seorang pun pernah memutuskan bahwa ia boleh.

    Daftar aktivitas sudah lebih dulu ditutup untuk level 4 justru supaya
    tidak menjadi pintu belakang ke angka yang sama; membiarkan pintu
    depannya terbuka membuat penutupan itu tidak ada artinya.
    """
    from utils.permission import MODUL_WILAYAH_MUTLAK

    assert "salary_slip" in MODUL_WILAYAH_MUTLAK
    assert "employees" in MODUL_WILAYAH_MUTLAK
    # Modul operasional TIDAK boleh ikut: General Manager memang perlu
    # melihatnya, dan memasukkannya ke sini akan mengunci level 4 dari
    # hampir seluruh sistem.
    for modul in ("purchase", "expenses", "supplier", "purchase_order"):
        assert modul not in MODUL_WILAYAH_MUTLAK, modul


def test_data_induk_boleh_dibuat_level_satu():
    """
    Pemasok dan barang boleh DIBUAT level 1, tetapi tidak diubah.

    Yang pertama menemukan pemasok atau barang baru adalah procurement, dan
    mereka level 1. Menahannya membuat data baru harus dititipkan ke orang
    lain sebelum dokumennya dapat dibuat.

    Mengubah tetap dibatasi karena akibatnya berbeda jauh: nama dan alamat
    pemasok tercetak di setiap dokumen yang menyebutnya, dan nama barang
    dibaca kembali dokumen lama lewat `item_id` — satu suntingan mengubah isi
    dokumen yang sudah ditandatangani.
    """
    for modul in ("supplier", "master_item"):
        assert required_level(modul, "create") == 1, modul
        assert required_level(modul, "update") >= 3, modul
        assert required_level(modul, "delete") >= 4, modul


def test_level_dibaca_tanpa_metode_dict():
    """
    Objek pengguna berupa Record dari `databases`, bukan dict.

    Record tidak punya `.get()`. Memanggilnya melempar AttributeError, dan
    permintaannya gagal dengan jejak tumpukan yang tidak menyebut sebabnya —
    galat yang sudah pernah terjadi sekali di rute ini.
    """
    rute = (Path(__file__).resolve().parents[1] / "routes" / "audit_log_routes.py").read_text()
    assert "current_user.get(" not in rute, "Record tidak punya .get()"
    assert "def _level(" in rute, "pembaca level yang tahan galat hilang"


def test_jejak_aktivitas_terbaca_semua_divisi():
    """
    Tanpa masuk modul umum, pengguna berdivisi tetap terkunci meski levelnya
    cukup — sementara yang belum punya divisi justru bisa membukanya.
    """
    for divisi in DEPARTMENT_MODULES:
        assert "audit_log" in modules_for({divisi}), divisi


def test_slip_gaji_dibatasi_divisi_bukan_nilai_khusus():
    """
    Slip gaji mengikuti tangga level biasa, dan yang membatasinya divisi.

    Bagian keuangan memerlukannya untuk PPh 21; menutupnya membuat pekerjaan
    itu berpindah ke luar sistem dan tidak meninggalkan jejak.
    """
    assert SPECIAL_ONLY not in MATRIX["salary_slip"]
    berwenang = {d for d, m in DEPARTMENT_MODULES.items() if "salary_slip" in m}
    # `konsultan` menyusul atas keputusan pemilik: rekapitulasi PPh 21 pada
    # halaman Perpajakan dihitung dari slip gaji, dan menutupnya memindahkan
    # pekerjaan itu ke luar sistem — tanpa jejak sama sekali.
    #
    # Baginya slip gaji HANYA-BACA; dijaga tes di bawah.
    assert berwenang == {"fat", "hrd", "konsultan"}


def test_konsultan_hanya_membaca_seluruh_wilayahnya():
    """
    Konsultan memeriksa, bukan mencatat.

    Ia pihak LUAR perusahaan. Satu pun dokumen tidak boleh berubah oleh
    tangannya — bukan soal percaya, melainkan soal siapa yang menanggung:
    perubahan oleh pihak luar tidak dapat dipertanggungjawabkan siapa pun
    di dalam.

    Diuji sebagai SELISIH terhadap UMUM, bukan sebagai daftar yang disalin.
    Daftar salinan akan tertinggal pada modul berikutnya yang ditambahkan ke
    wilayahnya, dan modul yang tertinggal itu justru menjadi satu-satunya
    yang dapat ia ubah — tanpa ada yang menyadarinya.
    """
    wilayah = DEPARTMENT_MODULES["konsultan"]
    assert wilayah - UMUM == DEPARTMENT_READ_ONLY["konsultan"]


def test_konsultan_tidak_menyentuh_uang_dan_orang():
    """
    Yang TIDAK boleh ada pada konsultan.

    Ditulis sebagai daftar tertutup supaya penambahan wilayah di kemudian
    hari berhenti di sini lebih dahulu, bukan diketahui setelah terpakai.
    """
    terlarang = {
        "bank",                     # rekening perusahaan
        "loan",                     # pinjaman
        "user",                     # pengguna beserta levelnya
        "purchase_order",           # isi perjanjian dengan pemasok
        "tender",                   # proses memilih pemasok
        "certificate_of_payment",
        "employee_profile",         # data pribadi karyawan
        "employee_form",
        "hr_recruitment",
    }
    bocor = DEPARTMENT_MODULES["konsultan"] & terlarang
    assert not bocor, f"konsultan tidak boleh memuat: {sorted(bocor)}"


# ---------------------------------------------------------------------------
# Divisi
# ---------------------------------------------------------------------------


def test_setiap_divisi_punya_nama_tampilan():
    for kode in DEPARTMENT_MODULES:
        assert kode in DEPARTMENT_LABELS, f"{kode} tidak punya nama"


def test_modul_umum_ada_di_semua_divisi():
    for kode, modul in DEPARTMENT_MODULES.items():
        assert UMUM <= modul, f"{kode} tidak memuat modul umum"


def test_modul_divisi_dikenali_matriks():
    for kode, modul in DEPARTMENT_MODULES.items():
        for m in modul:
            assert m in MATRIX, f"{kode} memuat modul tak dikenal: {m}"


def test_gabungan_divisi_bukan_irisan():
    """Yang menangani dua wilayah melihat keduanya."""
    gabungan = modules_for({"fat", "hrd"})
    assert DEPARTMENT_MODULES["fat"] <= gabungan
    assert DEPARTMENT_MODULES["hrd"] <= gabungan


def test_tanpa_divisi_tidak_dibatasi_wilayah():
    """Sengaja: supaya tidak mengunci siapa pun saat pemasangan."""
    assert boleh(3, set(), "salary_slip", "read") is True


# ---------------------------------------------------------------------------
# Contoh nyata
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "level,divisi,modul,aksi,harapan",
    [
        # Staf procurement
        (1, {"procurement"}, "purchase_order", "create", True),
        (1, {"procurement"}, "purchase_order", "delete", False),
        (1, {"procurement"}, "salary_slip", "read", False),
        (1, {"procurement"}, "bank", "read", False),
        # Supervisor membetulkan kekeliruan timnya
        (2, {"procurement"}, "purchase_order", "delete", True),
        # HRD melihat slip gaji, bukan rekening bank
        (3, {"hrd"}, "salary_slip", "read", True),
        (3, {"hrd"}, "bank", "read", False),
        # Bagian keuangan memerlukan slip gaji untuk PPh 21
        (3, {"fat"}, "salary_slip", "read", True),
        (3, {"fat"}, "tax", "create", True),
        # Wilayah tidak saling menembus
        (3, {"procurement"}, "salary_slip", "read", False),
        (3, {"procurement"}, "bank", "read", False),
        # Menghapus data induk perlu General Manager
        (3, {"procurement"}, "supplier", "delete", False),
        (4, {"procurement"}, "supplier", "delete", True),
        # Pemilik usaha tidak dibatasi divisi
        (5, set(), "bank", "delete", True),
        (5, set(), "audit_log", "read", True),
    ],
)
def test_contoh_penerapan(level, divisi, modul, aksi, harapan):
    assert boleh(level, divisi, modul, aksi) is harapan


# ---------------------------------------------------------------------------
# Batas data ditentukan isinya, bukan halaman yang menampilkannya
# ---------------------------------------------------------------------------


def test_rute_dijaga_sesuai_data_yang_dikembalikan():
    """
    Beberapa endpoint mengembalikan data yang lebih terbatas daripada modul
    yang menjaganya.

    Contohnya pernah terjadi: posisi kas dijaga `dashboard:read` (akses 1),
    padahal isinya nama bank, nomor rekening, dan saldo — yang untuk
    dibuka lewat daftar rekeningnya sendiri memerlukan akses 3. Staf
    procurement dapat membacanya hanya dengan membuka beranda.

    Pengujian ini menjaga penjagaan yang sudah dibetulkan agar tidak
    tergeser kembali ke modul halamannya.
    """
    import re
    from pathlib import Path

    HARUS = {
        "routes/dashboard_routes.py": ["bank"],
        "routes/calendar_routes.py": ["payment_outgoing"],
    }

    akar = Path(__file__).resolve().parents[1]
    for berkas, modul_wajib in HARUS.items():
        isi = (akar / berkas).read_text(encoding="utf-8")
        dijaga = set(re.findall(r'require\(\s*"([^"]+)"', isi))
        for m in modul_wajib:
            assert m in dijaga, f"{berkas} tidak lagi dijaga {m}"


def test_rincian_pembayaran_dijaga_seperti_pembayaran():
    """
    Rincian pembayaran memuat nama dan nomor rekening pembayar.

    Menjaganya dengan izin dokumen sumbernya (pembelian atau pengeluaran)
    membuat nomor rekening perusahaan terbaca oleh siapa pun yang boleh
    melihat dokumen itu.
    """
    import re
    from pathlib import Path

    akar = Path(__file__).resolve().parents[1]
    for berkas, penanda in (
        ("routes/purchase_routes.py", "get_payments_by_purchase_id"),
        ("routes/expenses_routes.py", "get_payments_by_expense_id"),
    ):
        isi = (akar / berkas).read_text(encoding="utf-8")
        potongan = isi[isi.index(penanda) : isi.index(penanda) + 500]
        assert 'require("payment_outgoing", "read")' in potongan, (
            f"{penanda} tidak dijaga payment_outgoing:read"
        )
