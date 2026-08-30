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

# Selisih rupiah yang masih dianggap LUNAS saat setoran dibandingkan dengan
# yang terutang.
#
# Yang terutang dihitung dari penjumlahan DPP × persen atas puluhan dokumen,
# jadi ia berekor pecahan; yang disetor adalah satu angka bulat yang diketik
# orang ke SSP. Keduanya nyaris tidak pernah sama persis — pada masa Juni 2026
# misalnya, terutangnya 825.186 dan setorannya 825.192, beda enam rupiah.
#
# Tanpa toleransi, setiap masa yang sudah lunas akan dilaporkan "lebih bayar
# Rp 6" — keterangan yang salah, dan yang membuat orang berhenti mempercayai
# angka yang benar di sebelahnya. Seribu rupiah cukup menampung pembulatan
# tanpa menelan kekurangan bayar yang sungguhan.
TOLERANSI_SETORAN = 1000


def status_setoran(selisih: float, setoran: float) -> str:
    """
    Keadaan setoran satu masa: "belum" | "lunas" | "kurang" | "lebih".

    Ditulis sebagai fungsi, bukan beberapa baris `if` di dalam controller:
    apakah satu masa sudah selesai adalah kesimpulan tentang uang, dan
    kesimpulan yang ditulis ulang di tempat kedua akan berselisih dengan yang
    pertama pada perubahan berikutnya — termasuk soal berapa selisih
    pembulatan yang masih dianggap lunas.

    `selisih` adalah yang TERUTANG pada masa itu (sudah termasuk kompensasi
    lebih bayar masa sebelumnya); `setoran` adalah yang sudah tercatat sebagai
    beban untuknya.

    Tanpa setoran hasilnya selalu "belum", termasuk ketika tidak ada yang
    terutang: masa nihil bukan "lunas" — ia tidak menagih apa-apa, dan
    menyebutnya lunas membuat layar mengabarkan pembayaran yang tidak ada.
    """
    if setoran <= 0:
        return "belum"
    sisa = selisih - setoran
    if abs(sisa) <= TOLERANSI_SETORAN:
        return "lunas"
    return "kurang" if sisa > 0 else "lebih"
