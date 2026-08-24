"""
Siapa yang boleh MENGUBAH purchase order, dan sampai kapan.

Keadaan yang mendorongnya: pemeriksa membuka dokumen, menemukan harga yang
keliru, lalu memberi tahu manajernya — dan manajer itu tidak dapat
membetulkannya sama sekali, sebab dokumennya bukan buatannya. Yang tersisa
hanya menunggu pembuatnya hadir, dan selama menunggu, dokumen yang salah tetap
berada di antrean pemeriksaan.

Batasnya PEMERIKSAAN, bukan persetujuan. Sebabnya ada di
`PurchaseOrderRepository.update`: menyunting dokumen yang sudah diperiksa
MENCABUT pemeriksaan itu diam-diam. Selama belum ada yang memeriksa, tidak ada
apa pun yang tercabut; sesudahnya, ada — dan pencabutan yang tidak disadari
membuat dokumen kembali ke antrean tanpa ada yang tahu mengapa.
"""

from utils.permission import boleh_mengubah_purchase_order as boleh

STAF = 1
PENYELIA = 2
MANAJER = 3
DIREKSI = 4
PEMILIK = 5


def test_manajer_boleh_selama_belum_diperiksa():
    """Inilah yang sebelumnya tidak bisa."""
    assert boleh(MANAJER, adalah_pembuat=False, sudah_diperiksa=False)


def test_manajer_TIDAK_boleh_setelah_diperiksa():
    """
    Sesudah diperiksa, seseorang sudah membaca harga dan volumenya lalu
    menyatakan benar. Menyuntingnya mencabut pernyataan itu tanpa suara.
    """
    assert not boleh(MANAJER, adalah_pembuat=False, sudah_diperiksa=True)


def test_pembuatnya_tetap_boleh_pada_keduanya():
    """
    Haknya tidak dikurangi aturan baru ini.

    Yang salah ketik biasanya yang mengisi, dan memaksanya meminta tolong
    orang lain membuat orang menghindari koreksi sama sekali.
    """
    for level in (STAF, PENYELIA, MANAJER):
        for diperiksa in (False, True):
            assert boleh(level, adalah_pembuat=True, sudah_diperiksa=diperiksa), (
                level,
                diperiksa,
            )


def test_level_empat_ke_atas_boleh_pada_keduanya():
    for level in (DIREKSI, PEMILIK):
        for diperiksa in (False, True):
            assert boleh(level, adalah_pembuat=False, sudah_diperiksa=diperiksa), (
                level,
                diperiksa,
            )


def test_di_bawah_manajer_tetap_tidak_boleh():
    """
    Yang bukan pembuatnya dan bukan manajer tidak mendapat apa-apa dari
    aturan ini — termasuk pada dokumen yang belum diperiksa.
    """
    for level in (STAF, PENYELIA):
        assert not boleh(level, adalah_pembuat=False, sudah_diperiksa=False), level
        assert not boleh(level, adalah_pembuat=False, sudah_diperiksa=True), level


def test_level_yang_tidak_terbaca_ditolak():
    """
    Bukan diperlakukan sebagai level tinggi.

    Nilai yang tidak terbaca datang dari token yang rusak atau kolom yang
    kosong; menganggapnya berwenang membuat kegagalan membaca berubah menjadi
    pemberian izin.
    """
    for ngawur in (None, "", "tiga", object()):
        assert not boleh(ngawur, adalah_pembuat=False, sudah_diperiksa=False), ngawur


def test_level_sebagai_teks_angka_tetap_terbaca():
    # Sebagian jalur meneruskan levelnya apa adanya dari basis data.
    assert boleh("3", adalah_pembuat=False, sudah_diperiksa=False)
    assert not boleh("3", adalah_pembuat=False, sudah_diperiksa=True)
    assert boleh("4", adalah_pembuat=False, sudah_diperiksa=True)


def test_pembuat_yang_tidak_dikenali_tidak_menaikkan_izin():
    # `adalah_pembuat` dihitung pemanggilnya; nilai bawaannya harus yang
    # paling sempit.
    assert not boleh(MANAJER, sudah_diperiksa=True)
