"""
Batas dan tetapan yang berlaku bagi SELURUH laporan pajak.

Ditaruh terpisah supaya batas yang sama tidak ditulis ulang di tiap
repository. Batas yang disalin adalah batas yang suatu hari akan berbeda di
salah satu salinannya, dan laporan pajak yang salah satu sumbernya memakai
batas berbeda tetap menghasilkan angka yang tampak masuk akal — itulah yang
membuatnya sulit ketahuan.
"""

from datetime import date


# MASA PAJAK PALING AWAL yang diakui sistem untuk laporan PPN.
#
# Data sebelum 2025 berasal dari era e-Faktur lama, tidak lengkap, dan tidak
# dapat dikonfirmasi lagi — pindahan sistem memotong pencatatan pada 2024 dan
# faktur-faktur sebelumnya tidak pernah masuk. Menyajikannya seolah-olah utuh
# lebih berbahaya daripada tidak menyajikannya: angka yang tampil akan dibaca
# sebagai posisi pajak yang sebenarnya, padahal ia hanya potongan dari
# separuh data.
#
# Batas ini berlaku pada DUA tempat sekaligus, dan keduanya perlu:
#
#   * rincian per masa — masa sebelum batas tidak mengembalikan baris apa pun;
#   * total per bulan yang dipakai menghitung kompensasi lebih bayar antar
#     masa — bila yang ini tidak ikut dibatasi, data lama tetap ikut
#     menggeser posisi masa sekarang secara diam-diam, justru pada angka yang
#     paling tidak terlihat asal-usulnya.
#
# Dibandingkan terhadap MASA PAJAK EFEKTIF (`COALESCE(masa, date)`), bukan
# tanggal dokumen: faktur pengganti bertanggal 2025 yang masanya 2024 tetap
# milik masa 2024, dan memang tidak ikut.
MASA_PAJAK_AWAL = date(2025, 1, 1)

# Bentuk tahun, untuk dipakai layar dan pesan.
TAHUN_PAJAK_AWAL = MASA_PAJAK_AWAL.year
