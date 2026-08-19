"""
Kolom yang tampak sebagai kunci alami tetapi tidak dijaga `UniqueConstraint`.

Nomor dokumen dan token adalah dua hal yang paling mahal bila kembar: nomor
PO yang sama membuat dua dokumen tidak dapat dibedakan vendor, dan token yang
sama membuat satu orang membuka data orang lain.

Keduanya tidak akan pernah menghasilkan galat. Aplikasinya menerima, datanya
tersimpan, dan yang menemukannya adalah orang yang kebetulan membandingkan.

CATATAN PENTING: pemeriksa ini membaca MODEL, bukan basis datanya.
`create_all` tidak mengubah tabel yang sudah ada — batasan yang ditambahkan
ke model TIDAK terpasang sendiri pada basis data yang sudah berjalan. Setiap
penambahan di sini harus disertai `ALTER TABLE` yang dijalankan terpisah.
"""

import re
import sys
from glob import glob

#: Kolom yang WAJIB unik, beserta alasannya.
#:
#: Daftar yang disebut satu per satu, bukan ditebak dari nama kolomnya: nama
#: karyawan dan nama barang boleh kembar, dan menandainya membuat pemeriksa
#: ini berisik terhadap hal yang memang benar.
WAJIB = {
    ("projects", "code"): "kode proyek dipakai seluruh dokumen",
    ("purchase_orders", "name"): "nomor PO yang sudah beredar ke vendor",
    ("sales_invoices", "name"): "nomor faktur yang dirujuk pelanggan",
    ("employee_form_invites", "token"): "tautan pengisian data karyawan",
    ("hr_candidates", "token"): "tautan ujian pelamar",
}


def periksa(akar: str = "models") -> list[str]:
    masalah = []

    for p in sorted(glob(f"{akar}/*.py")):
        s = open(p, errors="ignore").read()
        for m in re.finditer(r'Table\(\s*["\'](\w+)["\']([\s\S]*?)\n\)', s):
            tabel, isi = m.group(1), m.group(2)

            unik = set(re.findall(r'UniqueConstraint\(\s*["\'](\w+)["\']', isi))
            unik |= set(
                re.findall(
                    r'Column\(\s*["\'](\w+)["\'][^)]*unique\s*=\s*True', isi
                )
            )

            for (t, kolom), alasan in WAJIB.items():
                if t != tabel:
                    continue
                if kolom in unik:
                    continue
                masalah.append(
                    f"{tabel}.{kolom} tanpa UniqueConstraint — {alasan}"
                )

    return masalah


if __name__ == "__main__":
    h = periksa()
    print(f"kunci alami tanpa batasan: {len(h)}")
    print()
    for x in h[:20]:
        print(f"  {x}")
    sys.exit(1 if h else 0)
