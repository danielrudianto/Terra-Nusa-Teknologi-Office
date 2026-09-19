"""
Purchase order punya TIGA status, bukan dua.

KENAPA INI BERUBAH

"Draf" dulu memuat dua keadaan yang sangat berbeda: dokumen yang belum
disentuh siapa pun, dan dokumen yang sudah diperiksa dan tinggal menunggu
persetujuan. Di daftar keduanya tampil dengan lencana kuning yang sama —
yang kedua ditambah lencana "Diperiksa" di sebelahnya, sehingga satu baris
menyatakan dua hal yang saling bertentangan.

Akibatnya pada penyaring lebih buruk lagi: memilih "Draf" tidak pernah
menjawab "mana yang menunggu saya", karena hasilnya bercampur dengan yang
sudah selesai diperiksa.

YANG DIJAGA DI SINI

1. Ketiganya SALING LEPAS — satu dokumen cocok dengan tepat satu status.
2. Ketiganya MENUTUPI SEMUANYA — tidak ada dokumen yang tidak cocok dengan
   satu pun pilihan. Dokumen yang jatuh di celah itu tidak akan pernah
   tampil pada penyaring mana pun, dan hilangnya tidak menghasilkan galat.

Diuji dengan membaca SUMBERNYA: kueri daftar hanya dapat diuji perilakunya
terhadap basis data sungguhan, dan gerbang CI berjalan tanpa basis data.
"""

import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _badan_penyaring() -> str:
    jalur = os.path.join(AKAR, "repository", "purchase_order_repository.py")
    sumber = open(jalur, encoding="utf-8").read()
    awal = sumber.index('if status == "draft":')
    akhir = sumber.index("if checked is not None:", awal)
    return sumber[awal:akhir]


def test_status_diperiksa_ada_sebagai_penyaring_tersendiri():
    badan = _badan_penyaring()
    assert 'status == "checked"' in badan, (
        "penyaring `checked` hilang — pilihan 'Diperiksa' di layar akan "
        "mengirim status yang tidak dikenali server, dan yang kembali "
        "SELURUH daftar tanpa disaring sama sekali"
    )


def test_draf_berarti_BELUM_diperiksa():
    """
    Tanpa syarat `isChecked == False`, "Draf" tetap memuat dokumen yang
    sudah diperiksa — dan dua pilihan penyaring menghasilkan dokumen yang
    sama, tanpa apa pun yang menandainya.
    """
    badan = _badan_penyaring()
    draf = badan[badan.index('if status == "draft":') : badan.index('elif status == "checked":')]
    assert "isApproved == False" in draf
    assert "isChecked == False" in draf, (
        "'Draf' masih memuat dokumen yang sudah diperiksa"
    )


def test_diperiksa_berarti_belum_disetujui_TAPI_sudah_diperiksa():
    badan = _badan_penyaring()
    awal = badan.index('elif status == "checked":')
    blok = badan[awal : badan.index('elif status == "approved":')]
    assert "isApproved == False" in blok, (
        "'Diperiksa' ikut memuat dokumen yang sudah disetujui — dua status "
        "yang menampilkan dokumen yang sama"
    )
    assert "isChecked == True" in blok


def test_ketiganya_menutupi_seluruh_kemungkinan():
    """
    Dokumen punya dua penanda biner, jadi ada empat kemungkinan. Yang
    disetujui-tetapi-belum-diperiksa tidak dapat terjadi lewat alur
    aplikasinya, sehingga tiga penyaring cukup — tetapi hanya bila
    'approved' TIDAK ikut menuntut `isChecked`, supaya dokumen lama yang
    terlanjur disetujui tanpa tanda periksa tetap tampil.
    """
    badan = _badan_penyaring()
    disetujui = badan[badan.index('elif status == "approved":') :]
    assert "isApproved == True" in disetujui
    assert "isChecked" not in disetujui, (
        "'Disetujui' ikut menyaring `isChecked` — dokumen lama yang "
        "disetujui sebelum tahap pemeriksaan ada akan hilang dari daftar, "
        "dan tidak akan tampil pada pilihan mana pun"
    )
