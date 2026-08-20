"""
Masa retensi proyek — antara BAST 1 dan BAST 2.

Sebelumnya proyek hanya punya tiga keadaan, dinyatakan dua penanda. Proyek
yang sudah diserahkan tetapi masih dalam masa pemeliharaan tidak punya tempat:
menandainya "selesai" menghilangkan jejak retensinya, membiarkannya "berjalan"
membuatnya tidak dapat dibedakan dari pekerjaan yang masih dikerjakan.

Yang dijaga di sini gabungan penandanya. Tiga boolean punya delapan gabungan
dan hanya empat yang berarti; empat sisanya harus tidak mungkin terbentuk,
sebab proyek yang terhitung pada dua penyaring sekaligus membuat penjumlahan
di dua layar berbeda tanpa ada satu pun yang tampak salah.
"""

from controllers.project_controller import _selaraskan_keadaan as rapikan
from models.project_model import projects_table


def test_kolomnya_ada():
    assert "isRetention" in {c.name for c in projects_table.columns}


def test_retensi_tetap_aktif():
    """
    Proyeknya BELUM selesai.

    Masa pemeliharaan masih berjalan dan perbaikan yang timbul masih
    dibebankan ke sana. Mematikan `isActive` mengeluarkannya dari setiap
    pemilih proyek — sehingga biaya perbaikannya tidak punya tempat dicatat.
    """
    hasil = rapikan({"isActive": True, "isCancelled": False, "isRetention": True})
    assert hasil["isActive"] is True
    assert hasil["isRetention"] is True


def test_batal_mematikan_retensi():
    """Proyek yang dibatalkan tidak pernah sampai ke BAST 1."""
    hasil = rapikan({"isCancelled": True, "isRetention": True})
    assert hasil["isCancelled"] is True
    assert hasil["isActive"] is False
    assert hasil["isRetention"] is False


def test_selesai_mematikan_retensi():
    """
    Selesai berarti BAST 2 sudah lewat; retensinya sudah berakhir.

    Dibiarkan, proyek yang sama muncul pada penyaring "selesai" DAN pada
    penyaring "tunggu retensi".
    """
    hasil = rapikan({"isActive": False, "isRetention": True})
    assert hasil["isActive"] is False
    assert hasil["isRetention"] is False


def test_mengaktifkan_kembali_tidak_menyalakan_retensi_sendiri():
    """
    Retensi adalah tahap yang ditentukan orang, bukan akibat sampingan dari
    mengaktifkan kembali sebuah proyek.

    Muatannya `isActive=True` SAJA. Percobaan pertama mengirim `isActive` dan
    `isCancelled` sama-sama benar dan mengharapkan proyeknya aktif kembali —
    padahal `isCancelled` justru yang didahulukan, tepat seperti yang tertulis
    pada `_selaraskan_keadaan`. Yang gagal pengujiannya, bukan aturannya.
    """
    hasil = rapikan({"isActive": True})
    assert hasil["isActive"] is True
    assert hasil["isCancelled"] is False
    assert "isRetention" not in hasil


def test_batal_didahulukan_atas_aktif():
    # Keadaan yang lebih spesifik menang; ini yang membuat "aktif sekaligus
    # batal" tidak pernah terbentuk.
    hasil = rapikan({"isActive": True, "isCancelled": True})
    assert hasil["isCancelled"] is True
    assert hasil["isActive"] is False
    assert hasil["isRetention"] is False


def test_muatan_tanpa_penanda_tidak_disentuh():
    """
    Mengubah nama proyek tidak boleh ikut mengubah keadaannya.

    Muatan pembaruan hanya memuat kolom yang dikirim layar; menambahkan
    penanda yang tidak diminta akan menimpa keadaan yang sudah benar.
    """
    hasil = rapikan({"name": "Proyek Uji"})
    assert hasil == {"name": "Proyek Uji"}


def test_keempat_gabungan_yang_berarti_bertahan():
    """Yang sah tidak boleh ikut dirapikan menjadi sesuatu yang lain."""
    sah = [
        {"isActive": True, "isCancelled": False, "isRetention": False},
        {"isActive": True, "isCancelled": False, "isRetention": True},
        {"isActive": False, "isCancelled": False, "isRetention": False},
        {"isActive": False, "isCancelled": True, "isRetention": False},
    ]
    for muatan in sah:
        assert rapikan(dict(muatan)) == muatan, muatan
