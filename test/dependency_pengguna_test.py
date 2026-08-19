"""
Dependency pengguna tidak boleh dianotasi sebagai `int`.

`require()` dan `get_current_user()` mengembalikan PENGGUNANYA — sebuah
`Record` dari pustaka `databases` — bukan id-nya. Menulis

    user_id: int = Depends(require("asset", "update"))

tidak mengubah apa pun: FastAPI tidak memeriksa, apalagi mengonversi, nilai
yang dikembalikan sebuah dependency. Anotasi `int` di situ hanya keterangan
yang tidak pernah ditagih, dan `Record` utuh itu mengalir ke lapisan
berikutnya sampai ada yang menolaknya:

    updatedBy Input should be a valid integer [type=int_type,
    input_value=<databases.backends...Record object>]

Galat itu menyebut kolom yang tidak pernah diisi dari layar, sehingga yang
membacanya mencari-cari pada isian yang baru saja ia ubah. Sudah terjadi pada
pembaruan aset.

Diperiksa dari sumbernya: yang dijaga adalah bentuk penulisannya, dan bentuk
sudah dapat dibaca tanpa menjalankan apa pun.
"""

import os
import re
from glob import glob

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Parameter yang nilainya berasal dari dependency pengguna, beserta
#: anotasinya. Menangkap `nama: ANOTASI = Depends(require(...))` maupun
#: `Depends(get_current_user)`.
POLA = re.compile(
    r"""(\w+)\s*:\s*([^=\n]+?)\s*=\s*Depends\(\s*(require\(|get_current_user)""",
)

#: Anotasi yang jelas keliru untuk sebuah pengguna.
SALAH = ("int", "str", "float")


def _berkas_rute():
    return sorted(glob(os.path.join(AKAR, "routes", "*.py")))


def _tanpa_komentar(isi: str) -> str:
    """
    Baris komentar dibuang sebelum dipindai.

    Keterangan yang MENGUTIP bentuk yang salah — dan keterangan semacam itu
    memang ditulis tepat di sebelah perbaikannya — akan tertangkap sebagai
    pelanggaran, sehingga berkas yang sudah benar dilaporkan salah.
    """
    return "\n".join(
        b for b in isi.splitlines() if not b.lstrip().startswith("#")
    )


def test_ada_berkas_yang_diperiksa():
    """Penjaga bagi penjaganya: daftar kosong akan lulus tanpa memeriksa apa pun."""
    assert _berkas_rute()


def test_dependency_pengguna_tidak_dianotasi_angka():
    temuan = []
    for p in _berkas_rute():
        isi = _tanpa_komentar(open(p, encoding="utf-8").read())
        for baris, (nama, anotasi, _) in enumerate(POLA.findall(isi), start=1):
            if anotasi.strip() in SALAH:
                temuan.append(f"{os.path.basename(p)}: {nama}: {anotasi.strip()}")
    assert not temuan, (
        "dependency pengguna dianotasi sebagai nilai sederhana; "
        "pakai `Annotated[User, Depends(...)]` lalu ambil `['id']` — " + str(temuan)
    )
