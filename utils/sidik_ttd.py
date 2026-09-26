"""
SIDIK TANDA TANGAN — mengenali tanda tangan yang TERLALU MIRIP.

Apa yang alat ini bisa, dan apa yang TIDAK. Ini perlu dibaca sebelum
mempercayainya:

  BISA   mengenali SALINAN — tangkapan layar tanda tangan orang lain yang
         diunggah ulang, hasil jiplakan di atas gambar aslinya, atau satu
         gambar yang dipakai dua akun. Inilah bentuk pemalsuan yang paling
         mudah dilakukan di aplikasi: tidak perlu keterampilan apa pun.

  TIDAK  mengenali TIRUAN TANGAN yang digambar ulang dengan mata. Pikselnya
         berbeda, jadi sidiknya pun berbeda, sekalipun bagi manusia keduanya
         tampak sama. Tidak ada cara mengubah itu dari sebuah gambar; yang
         dapat membedakannya adalah dinamika goresan (tekanan dan waktu per
         titik), dan itu pun bidang penelitian, bukan pemeriksaan sederhana.

Karena itu hasilnya MENANDAI, tidak pernah MENOLAK. Dua orang yang sama-sama
menandatangani dengan coretan sederhana memang dapat berkemiripan tinggi
tanpa seorang pun berniat buruk — dan menolak tanda tangan orang jujur pada
fitur yang WAJIB dimiliki adalah kegagalan yang lebih buruk daripada
melewatkan satu kemiripan. Yang memutuskan tetap manusia: penandanya muncul
di layar persetujuan level 5.

CARANYA

`dHash` 64 bit atas MASKER TINTA, bukan atas gambarnya apa adanya:

  1. Gambar ditimpakan ke latar PUTIH. Tanda tangan disimpan dengan latar
     tembus pandang; tanpa langkah ini, PNG yang sama dapat menghasilkan
     sidik berbeda hanya karena pembacanya memperlakukan alfa secara lain.
  2. Dipotong ke KOTAK TINTA-nya. Tanpa pemotongan, yang paling menentukan
     sidiknya adalah DI MANA orang membubuhkan tanda tangannya di papan —
     dua tanda tangan identik di sudut berbeda akan tampak tidak mirip.
  3. Diperkecil ke 9x8 lalu tiap piksel dibandingkan dengan tetangga
     kanannya. Yang direkam arah perubahan terang-gelap, bukan nilainya,
     sehingga tebal garis dan besar gambar tidak mengubah hasilnya.
"""

import io
from PIL import Image, ImageOps

#: Lebar+1 x tinggi petak pembanding. 9x8 -> 8x8 perbandingan = 64 bit.
LEBAR = 9
TINGGI = 8

#: Di atas nilai ini sebuah piksel dihitung sebagai tinta.
AMBANG_TINTA = 24

#: Kemiripan yang DITANDAI kepada penyetuju.
#:
#: 64 bit; dua tanda tangan yang tidak berhubungan rata-rata berjarak sekitar
#: 32 bit (separuh). Jarak 10 bit ke bawah berarti keduanya sangat jarang
#: terjadi secara kebetulan.
AMBANG_MIRIP = 0.84  # jarak <= ~10 bit

#: Kemiripan yang hampir pasti SALINAN, bukan kebetulan.
AMBANG_SANGAT_MIRIP = 0.92  # jarak <= ~5 bit


def sidik(data: bytes) -> int | None:
    """
    Sidik 64 bit sebuah PNG tanda tangan. `None` bila gambarnya tanpa tinta.

    Mengembalikan `None` — bukan 0 — untuk gambar kosong. Nol adalah sidik
    yang sah (petak yang seluruhnya rata), dan menyamakan keduanya membuat
    setiap gambar kosong dinyatakan "sangat mirip" dengan gambar kosong lain.
    """
    try:
        gambar = Image.open(io.BytesIO(data))
    except Exception:
        return None

    gambar = gambar.convert("RGBA")
    latar = Image.new("RGBA", gambar.size, (255, 255, 255, 255))
    latar.alpha_composite(gambar)
    tinta = ImageOps.invert(latar.convert("L"))

    kotak = tinta.point(lambda v: 255 if v >= AMBANG_TINTA else 0).getbbox()
    if not kotak:
        return None
    tinta = tinta.crop(kotak)

    kecil = tinta.resize((LEBAR, TINGGI), Image.BOX)
    # `getdata()` usang sejak Pillow 12 dan hilang di 14; `tobytes()` ada di
    # keduanya dan mengembalikan hal yang sama untuk citra 8-bit satu kanal.
    piksel = list(kecil.tobytes())

    bit = 0
    for baris in range(TINGGI):
        for kolom in range(LEBAR - 1):
            kiri = piksel[baris * LEBAR + kolom]
            kanan = piksel[baris * LEBAR + kolom + 1]
            bit = (bit << 1) | (1 if kiri > kanan else 0)
    return bit


def jarak(a: int | None, b: int | None) -> int | None:
    """Jarak Hamming dua sidik, 0..64. `None` bila salah satunya tidak ada."""
    if a is None or b is None:
        return None
    return bin((int(a) ^ int(b)) & ((1 << 64) - 1)).count("1")


def kemiripan(a: int | None, b: int | None) -> float | None:
    """Kemiripan 0..1. `None` bila tidak dapat dibandingkan."""
    d = jarak(a, b)
    if d is None:
        return None
    return 1 - d / 64


def tingkat(nilai: float | None) -> str | None:
    """Sebutan untuk sebuah kemiripan: `sangat_mirip`, `mirip`, atau None."""
    if nilai is None:
        return None
    if nilai >= AMBANG_SANGAT_MIRIP:
        return "sangat_mirip"
    if nilai >= AMBANG_MIRIP:
        return "mirip"
    return None
